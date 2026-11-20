"use client";

import Link from "next/link";
import { Timeline } from "@/claims/Timeline";
import { t } from "@/i18n";
import { formatDateOnly } from "@/lib/format";
import { InviteToPay } from "@/payment/InviteToPay";
import { ErrorState, LoadingState } from "@/ui/states";
import { CLAIM_STATUS, CONTRIBUTION_STATUS } from "@/ui/tones";
import { Icon, Money, Pill } from "@/ui/ui";
import { contributionLine, contributionTitle } from "./describe";
import { useClaims, useContributions, useTimeZone, useTracking } from "./queries";

/** Dernier dossier et sa frise (planche : « Mon remboursement »). */
export function LatestClaimPanel() {
  const claims = useClaims();
  const latest = claims.data?.pages[0]?.items[0] ?? null;
  const tracking = useTracking(latest?.id ?? null);
  const timeZone = useTimeZone();

  if (claims.isPending) return <LoadingState label={t("loading.claims")} rows={4} />;
  if (claims.isError) return <ErrorState title={t("error.title.claims")} error={claims.error} onRetry={() => void claims.refetch()} retrying={claims.isFetching} />;
  if (!latest) {
    return (
      <section className="panel" aria-labelledby="latest-t">
        <div className="panel-h">
          <h2 className="panel-t" id="latest-t">
            {t("home.claim.title")}
          </h2>
        </div>
        <p className="pad">{t("claims.empty.text")}</p>
      </section>
    );
  }
  return (
    <section className="panel" aria-labelledby="latest-t" data-testid="latest-claim">
      <div className="panel-h">
        <h2 className="panel-t" id="latest-t">
          {t("home.claim.title")}
        </h2>
        <Pill look={CLAIM_STATUS[latest.status]} />
      </div>
      <div className="pad">
        <div className="rb-head">
          <b>{latest.provider_name}</b>
          <Money amount={latest.covered_xof} />
          <span className="rb-meta">
            {t("claim.forOn", { name: latest.beneficiary_given_name, date: formatDateOnly(latest.service_date) })} · <span className="id">{latest.claim_number}</span>
          </span>
        </div>
        {tracking.data ? <Timeline steps={tracking.data.steps} timeZone={timeZone} labelledBy="latest-t" /> : null}
        {tracking.isError ? <ErrorState title={t("error.title.tracking")} error={tracking.error} onRetry={() => void tracking.refetch()} retrying={tracking.isFetching} /> : null}
        <Link className="link-row" href={`/soins/${latest.id}`}>
          <span>{t("home.claim.follow")}</span>
          <Icon name="chev" />
        </Link>
      </div>
    </section>
  );
}

/** Cotisation du mois : échéance à payer (et l'invitation d'un proche), sinon la dernière payée. */
export function ContributionPanel() {
  const query = useContributions();
  const timeZone = useTimeZone();
  if (query.isPending) return <LoadingState label={t("loading.contributions")} rows={2} />;
  if (query.isError) return <ErrorState title={t("error.title.contributions")} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} />;
  const shown = query.data.next_due ?? query.data.items[0] ?? null;
  if (!shown) return null;
  return (
    <section className="panel" aria-labelledby="contrib-t" data-testid="home-contribution">
      <div className="panel-h">
        <h2 className="panel-t" id="contrib-t">
          {contributionTitle(shown)}
        </h2>
        <Pill look={CONTRIBUTION_STATUS[shown.status]} />
      </div>
      <div className="pad stack">
        <p>
          {contributionLine(shown, timeZone)} · <Money amount={shown.amount_xof} />
        </p>
        {query.data.next_due ? <InviteToPay contribution={query.data.next_due} /> : <p>{t("contributions.upToDate")}</p>}
      </div>
    </section>
  );
}
