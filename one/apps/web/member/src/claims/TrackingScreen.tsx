"use client";

import Link from "next/link";
import { useEffect } from "react";
import { t } from "@/i18n";
import { formatDateOnly } from "@/lib/format";
import { track } from "@/lib/track";
import { useTimeZone, useTracking } from "@/member/queries";
import { ErrorState, LoadingState } from "@/ui/states";
import { CLAIM_STATUS } from "@/ui/tones";
import { Icon, Money, Pill, ScreenTitle } from "@/ui/ui";
import { Timeline } from "./Timeline";

/**
 * Suivre mon remboursement (getMyClaimTracking) : le montant pris en charge en héros, puis la
 * frise demande reçue → accordée → virement → reçu. Aucun acte, motif ni score : le contrat
 * n'en renvoie pas (seulement le code public de la règle).
 */
export function TrackingScreen({ claimId }: { claimId: string }) {
  const query = useTracking(claimId);
  const timeZone = useTimeZone();
  const claim = query.data?.claim;
  const loaded = query.isSuccess;
  // Mesure produit : un suivi consulté (aucun identifiant de dossier n'est envoyé).
  useEffect(() => {
    if (loaded) track("claim_tracking_viewed");
  }, [loaded, claimId]);
  return (
    <div className="m-body m-single" data-testid="tracking-screen">
      <div className="m-col">
        <Link className="link-row link-back" href="/soins">
          <Icon name="back" />
          <span>{t("tracking.back")}</span>
        </Link>
        <p className="eyebrow">{claim ? claim.provider_name : t("tracking.eyebrow")}</p>
        <ScreenTitle>{t("tracking.title")}</ScreenTitle>
        {query.isPending ? <LoadingState label={t("loading.tracking")} rows={5} /> : null}
        {query.isError ? <ErrorState title={t("error.title.tracking")} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
        {query.data && claim ? (
          <>
            <section className="panel pay-hero" aria-labelledby="covered-t">
              <div className="hero-top">
                <span className="pay-hero-label" id="covered-t">
                  {t("claim.covered")}
                </span>
                <Pill look={CLAIM_STATUS[claim.status]} testId="claim-status" />
              </div>
              <Money amount={claim.covered_xof} className="money-display" />
              <dl className="rows-dl">
                <dt>{t("claim.total")}</dt>
                <dd>
                  <Money amount={claim.total_xof} />
                </dd>
                <dt>{t("claim.patient")}</dt>
                <dd>
                  <Money amount={claim.patient_share_xof} />
                </dd>
                <dt>{t("claim.beneficiary")}</dt>
                <dd>{claim.beneficiary_given_name}</dd>
                <dt>{t("claim.serviceDate")}</dt>
                <dd>{formatDateOnly(claim.service_date)}</dd>
                <dt>{t("claim.number")}</dt>
                <dd className="id">{claim.claim_number}</dd>
              </dl>
            </section>
            <section className="panel" aria-labelledby="steps-t">
              <div className="panel-h">
                <h2 className="panel-t" id="steps-t">
                  {t("tracking.steps")}
                </h2>
              </div>
              <div className="pad">
                <Timeline steps={query.data.steps} timeZone={timeZone} labelledBy="steps-t" />
              </div>
            </section>
          </>
        ) : null}
      </div>
    </div>
  );
}
