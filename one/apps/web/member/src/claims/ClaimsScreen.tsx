"use client";

import Link from "next/link";
import type { MyClaim } from "@/api/types";
import { t } from "@/i18n";
import { formatDateOnly } from "@/lib/format";
import { useClaims } from "@/member/queries";
import { EmptyState, ErrorState, LoadingState } from "@/ui/states";
import { CLAIM_STATUS } from "@/ui/tones";
import { Button, Icon, Money, Pill, ScreenTitle } from "@/ui/ui";

function ClaimRow({ claim }: { claim: MyClaim }) {
  return (
    <li>
      <Link className="claim-row" href={`/soins/${claim.id}`} data-testid="claim-row">
        <span className="claim-main">
          <b>{claim.provider_name}</b>
          <span>{t("claim.forOn", { name: claim.beneficiary_given_name, date: formatDateOnly(claim.service_date) })}</span>
          <span className="id">{claim.claim_number}</span>
        </span>
        <span className="claim-side">
          <Pill look={CLAIM_STATUS[claim.status]} />
          <span className="claim-amount">
            <span className="sr-only">{t("claim.covered")}</span>
            <Money amount={claim.covered_xof} />
          </span>
        </span>
        <Icon name="chev" className="chev" />
      </Link>
    </li>
  );
}

/** Mes remboursements : dossiers du contrat, du plus récent au plus ancien (listMyClaims, paginé). */
export function ClaimsScreen() {
  const query = useClaims();
  const items = query.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <div className="m-body m-single" data-testid="claims-screen">
      <div className="m-col">
        <p className="eyebrow">{t("claims.eyebrow")}</p>
        <ScreenTitle>{t("claims.title")}</ScreenTitle>
        <p>{t("claims.lead")}</p>
        {query.isPending ? <LoadingState label={t("loading.claims")} rows={4} /> : null}
        {query.isError && items.length === 0 ? <ErrorState title={t("error.title.claims")} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} /> : null}
        {query.isSuccess && items.length === 0 ? <EmptyState title={t("claims.empty.title")}>{t("claims.empty.text")}</EmptyState> : null}
        {items.length > 0 ? (
          <ul className="panel rows" aria-label={t("claims.listLabel")}>
            {items.map((claim) => (
              <ClaimRow key={claim.id} claim={claim} />
            ))}
          </ul>
        ) : null}
        {query.isFetchNextPageError ? <ErrorState title={t("error.title.claimsMore")} error={query.error} onRetry={() => void query.fetchNextPage()} retrying={query.isFetchingNextPage} /> : null}
        {query.hasNextPage && !query.isFetchNextPageError ? (
          <Button variant="secondary" icon="chev" busy={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>
            {t("claims.more")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
