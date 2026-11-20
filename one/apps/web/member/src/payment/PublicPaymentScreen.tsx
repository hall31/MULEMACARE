"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "@/api/client";
import { problemCode, toUiError } from "@/api/errors";
import type { Checkout, PaymentChannel, PublicPaymentLink } from "@/api/types";
import { t, type MessageKey } from "@/i18n";
import { eurEquivalentCents, formatEurCents, formatMonthYear, formatParity, formatXof, withDe } from "@/lib/format";
import { queryKeys } from "@/member/queries";
import { ErrorState } from "@/ui/states";
import { BrandLogo, BrandName } from "@/brand/brand-context";
import { BrandMark, Button, Guilloche, Icon, Money, Notice, Seal, Skeleton, useDelayed } from "@/ui/ui";

function newKey(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

const MOBILE_MONEY: ReadonlySet<PaymentChannel> = new Set(["wave", "orange_money", "mtn_momo"]);

function channelLabel(channel: PaymentChannel): string {
  return t(`channel.${channel}` as MessageKey);
}

function PayHeader() {
  return (
    <header className="p-top">
      <BrandLogo fallback={<BrandMark />} />
      <b>
        <BrandName />
      </b>
      <span className="p-secure">
        <Icon name="lock" />
        {t("pay.secure")}
      </span>
    </header>
  );
}

/** Fin de parcours (payé, lien expiré, lien inconnu) : cachet + preuve ou explication + code. */
function Outcome({ kind, title, text, detail, code, testId }: { kind: "ok" | "crit" | "warn"; title: string; text: string; detail?: string; code?: string; testId: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => ref.current?.focus(), []);
  return (
    <div className={`outcome outcome-${kind}`} data-testid={testId} data-code={code}>
      <Seal kind={kind === "ok" ? "ok" : "crit"} animate={kind === "ok"} />
      <h1 ref={ref} tabIndex={-1} className="m-h1">
        {title}
      </h1>
      <p>{text}</p>
      {detail ? <p>{detail}</p> : null}
      {code ? <span className="code-chip id">{t("error.codeLabel", { code })}</span> : null}
    </div>
  );
}

type Finished = { kind: "done"; checkout: Checkout; channel: PaymentChannel } | { kind: "expired"; error: unknown };

function PayForm({ token, link, onFinished }: { token: string; link: PublicPaymentLink; onFinished: (finished: Finished) => void }) {
  const [channel, setChannel] = useState<PaymentChannel | null>(link.channels[0] ?? null);
  const [missing, setMissing] = useState(false);
  const keyRef = useRef<string | null>(null);
  const period = formatMonthYear(link.period_start);
  const amount = formatXof(link.amount_xof);

  const checkout = useMutation({
    mutationFn: (chosen: PaymentChannel) => {
      keyRef.current ??= newKey();
      return api.startCheckout(token, { channel: chosen }, keyRef.current);
    },
    onSuccess: (result: Checkout, chosen) => {
      // Une tentative aboutie ou échouée est close : la suivante aura sa propre clé.
      keyRef.current = null;
      if (result.status === "confirme") onFinished({ kind: "done", checkout: result, channel: chosen });
      else if (result.status === "en_attente" && result.redirect_url && result.redirect_url.startsWith("https://")) window.location.assign(result.redirect_url);
    },
    onError: (error) => {
      if (problemCode(error) === "PAY-03") onFinished({ kind: "expired", error });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!channel) {
      setMissing(true);
      return;
    }
    checkout.mutate(channel);
  };

  const pending = checkout.data?.status === "en_attente" ? checkout.data : null;
  const failed = checkout.data?.status === "echoue";
  const eur = formatEurCents(eurEquivalentCents(link.amount_xof));

  return (
    <form className="panel p-card" aria-labelledby="p-amt-t" onSubmit={submit} noValidate data-testid="pay-form">
      <Guilloche />
      <p className="p-label" id="p-amt-t">
        {t("pay.amountLabel")}
      </p>
      <Money amount={link.amount_xof} className="money-display p-amt" />
      <p className="p-conv" data-testid="pay-equivalent">
        {t("pay.equivalent", { eur, parity: formatParity() })}
      </p>
      <dl className="rows-dl">
        <dt>{t("pay.period")}</dt>
        <dd className="cap">{period}</dd>
        <dt>{t("pay.holder")}</dt>
        <dd>{link.holder_initials}</dd>
      </dl>
      <fieldset className="p-methods" aria-describedby={missing ? "pm-err" : undefined} disabled={checkout.isPending || pending !== null}>
        <legend>{t("pay.methods")}</legend>
        {link.channels.map((c) => (
          <label key={c} className="method">
            <input
              type="radio"
              name="channel"
              value={c}
              checked={channel === c}
              onChange={() => {
                setChannel(c);
                setMissing(false);
              }}
            />
            <span>
              <b>{channelLabel(c)}</b>
              <span>{t(MOBILE_MONEY.has(c) ? "pay.method.app" : (`pay.method.${c}` as MessageKey))}</span>
            </span>
            <Icon name={MOBILE_MONEY.has(c) ? "phone" : "wallet"} />
          </label>
        ))}
        {missing ? (
          <p id="pm-err" className="field-error" role="alert">
            <Icon name="alert" />
            {t("pay.choose")}
          </p>
        ) : null}
      </fieldset>
      {pending ? (
        <Notice tone="info" icon="clock" title={t(pending.redirect_url ? "pay.redirecting" : "pay.pending.title", { channel: channel ? channelLabel(channel) : "" })} testId="pay-pending">
          <p>{t("pay.pending.text", { channel: channel ? channelLabel(channel) : "" })}</p>
        </Notice>
      ) : null}
      {failed ? (
        <Notice tone="crit" role="alert" title={t("pay.failed.title")} testId="pay-failed">
          <p>{t("pay.failed.text")}</p>
        </Notice>
      ) : null}
      {checkout.isError ? <ErrorState title={t("error.title.checkout")} error={checkout.error} testId="checkout-error" /> : null}
      {pending ? null : (
        <Button type="submit" variant="primary" icon="lock" busy={checkout.isPending} className="btn-block" data-testid="pay-submit">
          {t(failed || checkout.isError ? "pay.retry" : "pay.submit", { amount })}
        </Button>
      )}
      <p className="p-trust">
        <Icon name="shield" />
        <span>{t("pay.trust")}</span>
      </p>
    </form>
  );
}

function PaySkeleton() {
  const shown = useDelayed(true);
  return (
    <div className="panel p-card p-card-sk" role="status" aria-live="polite" data-testid="pay-loading">
      <span className="sr-only">{t("loading.pay")}</span>
      {shown ? (
        <>
          <Skeleton width="40%" />
          <Skeleton width="70%" height="40px" />
          <Skeleton width="85%" />
          <Skeleton />
          <Skeleton />
        </>
      ) : null}
    </div>
  );
}

/**
 * Page publique du lien de paiement diaspora (getPublicPaymentLink, startCheckout ; sans compte,
 * aucun jeton envoyé). Montant en FCFA (devise locale du contrat) et équivalent indicatif en
 * euros à la parité fixe ; états payé, expiré ou déjà utilisé (410 PAY-03), introuvable (404).
 */
export function PublicPaymentScreen({ token }: { token: string }) {
  const query = useQuery({ queryKey: queryKeys.publicLink(token), queryFn: () => api.getPublicPaymentLink(token), staleTime: Infinity });
  const code = problemCode(query.error);
  const link = query.data;
  const [finished, setFinished] = useState<Finished | null>(null);

  let body;
  if (finished?.kind === "done" && link) {
    body = (
      <Outcome
        kind="ok"
        testId="pay-done"
        title={t("pay.done.title")}
        text={t("pay.done.text", { period: withDe(formatMonthYear(link.period_start)), initials: link.holder_initials, amount: formatXof(link.amount_xof) })}
        detail={t("pay.done.proof", { channel: channelLabel(finished.channel), reference: finished.checkout.payment_id.slice(0, 8).toUpperCase() })}
      />
    );
  } else if (finished?.kind === "expired") {
    const ui = toUiError(finished.error);
    body = <Outcome kind="warn" testId="pay-expired" title={t("pay.expired.title")} text={ui.text} detail={ui.detail} code={ui.code} />;
  } else if (code === "PAY-03") {
    const ui = toUiError(query.error);
    body = <Outcome kind="warn" testId="pay-expired" title={t("pay.expired.title")} text={ui.text} detail={ui.detail} code={ui.code} />;
  } else if (code === "NOT-01" || code === "VAL-01") {
    const ui = toUiError(query.error);
    body = <Outcome kind="crit" testId="pay-invalid" title={t("pay.invalid.title")} text={t("pay.invalid.text")} detail={ui.detail} code={ui.code} />;
  } else if (query.isError) {
    body = (
      <div className="p-error">
        <h1 className="m-h1">{t("pay.title.generic")}</h1>
        <ErrorState title={t("error.title.pay")} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} />
      </div>
    );
  } else {
    const period = link ? formatMonthYear(link.period_start) : null;
    const channels = link ? link.channels.map(channelLabel).join(", ") : "";
    body = (
      <>
        <div className="p-intro">
          <p className="eyebrow">{t("pay.eyebrow")}</p>
          <h1 className="m-h1 p-h1">{link && period ? t("pay.title", { period: withDe(period), initials: link.holder_initials }) : t("pay.title.generic")}</h1>
          <p className="p-lead">{link ? t("pay.lead", { initials: link.holder_initials }) : t("pay.lead.generic")}</p>
          <ol className="p-steps">
            <li>
              <div>
                <b>{t("pay.step1.title")}</b>
                {link ? t("pay.step1.text", { channels }) : null}
              </div>
            </li>
            <li>
              <div>
                <b>{t("pay.step2.title")}</b>
                {t("pay.step2.text")}
              </div>
            </li>
            <li>
              <div>
                <b>{link ? t("pay.step3.title", { amount: formatXof(link.amount_xof) }) : t("pay.step3.title.generic")}</b>
                {link ? t("pay.step3.text", { initials: link.holder_initials }) : null}
              </div>
            </li>
          </ol>
        </div>
        {link ? <PayForm token={token} link={link} onFinished={setFinished} /> : <PaySkeleton />}
      </>
    );
  }

  return (
    <div className="pay">
      <PayHeader />
      <main className="p-body" id="contenu" data-testid="pay-screen">
        {body}
      </main>
    </div>
  );
}
