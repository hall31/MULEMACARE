"use client";

import { t } from "@/i18n";
import { InviteToPay } from "@/payment/InviteToPay";
import { EmptyState, ErrorState, LoadingState } from "@/ui/states";
import { CONTRIBUTION_STATUS } from "@/ui/tones";
import { Money, Pill, ScreenTitle, Seal } from "@/ui/ui";
import { contributionLine, contributionPeriod, contributionTitle } from "./describe";
import { useContributions, useTimeZone } from "./queries";

/**
 * Mes cotisations (listMyContributions) : l'échéance à payer en tête, montant en héros, et
 * « Inviter un proche à payer » comme action principale ; puis l'historique.
 */
export function ContributionsScreen() {
  const query = useContributions();
  const timeZone = useTimeZone();
  const due = query.data?.next_due ?? null;
  const history = query.data?.items.filter((c) => c.id !== due?.id) ?? [];
  return (
    <div className="m-body" data-testid="contributions-screen">
      <div className="m-col">
        <p className="eyebrow">{t("contributions.eyebrow")}</p>
        <ScreenTitle>{t("contributions.title")}</ScreenTitle>
        {query.isPending ? <LoadingState label={t("loading.contributions")} rows={3} /> : null}
        {query.isError ? <ErrorState title={t("error.title.contributions")} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
        {query.isSuccess && query.data.items.length === 0 ? <EmptyState title={t("contributions.empty.title")}>{t("contributions.empty.text")}</EmptyState> : null}
        {due ? (
          <section className="panel pay-hero" aria-labelledby="due-t" data-testid="next-due">
            <div className="hero-top">
              <h2 className="pay-hero-label" id="due-t">
                {contributionTitle(due)}
              </h2>
              <Pill look={CONTRIBUTION_STATUS[due.status]} />
            </div>
            <Money amount={due.amount_xof} className="money-display" />
            <p>{contributionLine(due, timeZone)}</p>
            <p>{t("invite.lead")}</p>
            <InviteToPay contribution={due} primary />
          </section>
        ) : null}
        {query.isSuccess && !due && query.data.items.length > 0 ? (
          <div className="empty empty-ok" data-testid="up-to-date">
            <Seal kind="ok" />
            <b>{t("contributions.upToDate.title")}</b>
            <p>{t("contributions.upToDate")}</p>
          </div>
        ) : null}
      </div>
      <div className="m-col">
        {history.length > 0 ? (
          <section className="panel" aria-labelledby="history-t">
            <div className="panel-h">
              <h2 className="panel-t" id="history-t">
                {t("contributions.history")}
              </h2>
            </div>
            <ul className="rows" data-testid="contribution-history">
              {history.map((c) => (
                <li key={c.id} className="row">
                  <span className="row-main">
                    <b className="cap">{contributionPeriod(c)}</b>
                    <span>{contributionLine(c, timeZone)}</span>
                  </span>
                  <span className="row-side">
                    <Pill look={CONTRIBUTION_STATUS[c.status]} />
                    <Money amount={c.amount_xof} />
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  );
}
