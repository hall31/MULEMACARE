"use client";

import Link from "next/link";
import type { MessageKey } from "@/i18n";
import { t } from "@/i18n";
import { formatDateOnly } from "@/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/ui/states";
import { BENEFICIARY_CARD } from "@/ui/tones";
import { Icon, Pill, ScreenTitle } from "@/ui/ui";
import { useBeneficiaries } from "./queries";

function initials(given: string, family: string): string {
  return `${given.charAt(0)}${family.charAt(0)}`.toUpperCase();
}

/** Mes bénéficiaires (listMyBeneficiaries) : titulaire et ayants droit, état de leur carte. */
export function FamilyScreen() {
  const query = useBeneficiaries();
  const items = query.data?.items ?? [];
  return (
    <div className="m-body m-single" data-testid="family-screen">
      <div className="m-col">
        <p className="eyebrow">{t("family.eyebrow")}</p>
        <ScreenTitle>{t("family.title")}</ScreenTitle>
        <p>{t("family.lead")}</p>
        {query.isPending ? <LoadingState label={t("loading.family")} rows={3} /> : null}
        {query.isError ? <ErrorState title={t("error.title.family")} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
        {query.isSuccess && items.length === 0 ? <EmptyState title={t("family.empty.title")}>{t("family.empty.text")}</EmptyState> : null}
        {items.length > 0 ? (
          <ul className="panel rows" aria-label={t("family.listLabel")} data-testid="beneficiaries">
            {items.map((b) => {
              const name = `${b.given_name} ${b.family_name}`;
              const period = b.valid_to
                ? t("family.coveredBetween", { from: formatDateOnly(b.valid_from), to: formatDateOnly(b.valid_to) })
                : t("family.coveredSince", { from: formatDateOnly(b.valid_from) });
              return (
                <li key={b.person_id} className="row row-person" data-testid="beneficiary">
                  <span className="av av-md" aria-hidden="true">
                    {initials(b.given_name, b.family_name)}
                  </span>
                  <span className="row-main">
                    <b>{name}</b>
                    <span>
                      {t(`relationship.${b.relationship}` as MessageKey)} · {period}
                    </span>
                    <Pill look={BENEFICIARY_CARD[b.card_status]} />
                  </span>
                  {b.card_status === "aucune" ? null : (
                    <Link className="btn btn-secondary btn-auto" href={b.relationship === "titulaire" ? "/" : `/carte/${b.person_id}`} aria-label={t("family.showCardOf", { name })}>
                      <Icon name="card" />
                      <span>{t("family.showCard")}</span>
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
