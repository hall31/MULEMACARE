"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import type { MyContribution, PaymentLink } from "@/api/types";
import { t } from "@/i18n";
import { formatDate, formatMonthYear, withDe } from "@/lib/format";
import { track } from "@/lib/track";
import { useOnline, useTimeZone } from "@/member/queries";
import { ErrorState } from "@/ui/states";
import { Button, Icon, Notice, Seal } from "@/ui/ui";
import { browserShareCapabilities, copyLink, inviteMessage, shareInvite, whatsappUrl, type ShareOutcome } from "./share";

function newKey(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/**
 * « Inviter un proche à payer » (createMyPaymentLink) : crée le lien à usage unique, puis le
 * partage par le partage natif du téléphone, WhatsApp ou la copie. Une même tentative garde sa
 * clé d'idempotence : un nouvel essai après une coupure ne crée pas un deuxième lien.
 */
export function InviteToPay({ contribution, primary = false }: { contribution: MyContribution; primary?: boolean }) {
  const timeZone = useTimeZone();
  const online = useOnline();
  const keyRef = useRef<string | null>(null);
  const [outcome, setOutcome] = useState<ShareOutcome | null>(null);
  const [canShare, setCanShare] = useState(false);
  const linkRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => setCanShare(typeof navigator !== "undefined" && typeof navigator.share === "function"), []);

  const mutation = useMutation({
    mutationFn: () => {
      keyRef.current ??= newKey();
      return api.createMyPaymentLink(contribution.id, keyRef.current);
    },
    onSuccess: () => {
      keyRef.current = null;
      track("payment_link_created");
    },
  });

  useEffect(() => {
    if (mutation.data) resultRef.current?.focus();
  }, [mutation.data]);

  const link: PaymentLink | undefined = mutation.data;
  const period = withDe(formatMonthYear(contribution.period_start));

  if (!link) {
    return (
      <div className="stack" data-testid="invite">
        <Button
          variant={primary ? "primary" : "secondary"}
          icon="globe"
          busy={mutation.isPending}
          disabled={!online}
          aria-describedby={online ? undefined : `invite-offline-${contribution.id}`}
          onClick={() => mutation.mutate()}
          className="btn-block"
        >
          {t("invite.button")}
        </Button>
        {online ? null : (
          <p id={`invite-offline-${contribution.id}`} className="field-hint" data-testid="invite-offline">
            <Icon name="wifiOff" />
            <span>{t("invite.offline")}</span>
          </p>
        )}
        {mutation.isError ? <ErrorState title={t("error.title.invite")} error={mutation.error} onRetry={() => mutation.mutate()} retrying={mutation.isPending} testId="invite-error" /> : null}
      </div>
    );
  }

  const message = inviteMessage(contribution, link, timeZone);
  const shareData = { title: t("invite.shareTitle", { period }), text: message, url: link.url };
  const onShare = async () => setOutcome(await shareInvite(browserShareCapabilities(), shareData));
  const onCopy = async () => {
    const result = await copyLink(browserShareCapabilities(), link.url);
    setOutcome(result);
    if (result === "unavailable") linkRef.current?.select();
  };

  return (
    <div className="invite-done stack" data-testid="invite-link" ref={resultRef} tabIndex={-1}>
      <div className="success">
        <Seal kind="ok" animate />
        <div>
          <b>{t("invite.created")}</b>
          <p>{t("invite.until", { date: formatDate(link.expires_at, timeZone) })}</p>
        </div>
      </div>
      <div className="field-group">
        <label className="field-label" htmlFor={`link-${contribution.id}`}>
          {t("invite.linkLabel")}
        </label>
        <input ref={linkRef} id={`link-${contribution.id}`} className="field field-link" readOnly value={link.url} onFocus={(e) => e.currentTarget.select()} />
      </div>
      <div className="actions">
        {canShare ? (
          <Button variant={primary ? "primary" : "secondary"} icon="share" onClick={() => void onShare()} data-testid="invite-share">
            {t("invite.share")}
          </Button>
        ) : null}
        <a className="btn btn-secondary" href={whatsappUrl(message)} target="_blank" rel="noopener noreferrer" data-testid="invite-whatsapp">
          <Icon name="message" />
          <span>{t("invite.whatsapp")}</span>
        </a>
        <Button variant="secondary" icon="copy" onClick={() => void onCopy()} data-testid="invite-copy">
          {t("invite.copy")}
        </Button>
      </div>
      <p className="sr-live" role="status" aria-live="polite" data-testid="invite-feedback">
        {outcome === "copied" ? t("invite.copied") : outcome === "shared" ? t("invite.shared") : outcome === "unavailable" ? t("invite.unavailable") : ""}
      </p>
      <Notice tone="info" icon="info">
        <p>{t("invite.once")}</p>
      </Notice>
    </div>
  );
}
