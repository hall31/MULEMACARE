"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { useAccess, useClaims, type ClaimFilters } from "@/api/queries";
import type { ClaimStatus, ClaimSummary } from "@/api/types";
import { DataTable, type ColumnMeta } from "@/components/data-table";
import { EmptyState, ErrorState, LoadingRows, OpenPaletteButton, PageHeader, Panel } from "@/components/states";
import { ClaimStatusBadge, FraudBadge, RiskCell } from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/misc";
import { t, type MessageKey } from "@/i18n";
import { formatDateTime, formatMoney, initials } from "@/lib/format";
import { ClaimDrawer } from "./claim-drawer";

type FilterKey = "all" | "fraud" | ClaimStatus;

const FILTERS: { key: FilterKey; label: MessageKey }[] = [
  { key: "all", label: "claims.filterAll" },
  { key: "en_revue", label: "claims.filterReview" },
  { key: "fraud", label: "claims.filterFraud" },
  { key: "accordee_auto", label: "claims.filterAuto" },
  { key: "pieces_demandees", label: "claims.filterDocuments" },
  { key: "payee", label: "claims.filterPaid" },
  { key: "refusee", label: "claims.filterRejected" },
];

const STATUSES: readonly ClaimStatus[] = ["demandee", "accordee_auto", "en_revue", "pieces_demandees", "accordee", "refusee", "payee", "annulee"];

/** Filtres portés par l'URL : un lien partagé rouvre la même vue et le même dossier. */
function useClaimsUrlState() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const rawStatus = params.get("statut");
  const status = STATUSES.find((s) => s === rawStatus);
  const fraud = params.get("fraude") === "1";
  const active: FilterKey = fraud ? "fraud" : (status ?? "all");
  const claimId = params.get("dossier");

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) {
      if (v === null) next.delete(k);
      else next.set(k, v);
    }
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  return {
    filters: { status, fraudFlagged: fraud || undefined } satisfies ClaimFilters,
    active,
    claimId,
    setFilter: (key: FilterKey) =>
      update(
        key === "all"
          ? { statut: null, fraude: null }
          : key === "fraud"
            ? { statut: null, fraude: "1" }
            : { statut: key, fraude: null },
      ),
    openClaim: (id: string | null) => update({ dossier: id }),
  };
}

export function ClaimsView() {
  const { timezone } = useAccess();
  const state = useClaimsUrlState();
  const claims = useClaims(state.filters);
  const rows = useMemo(() => claims.data?.pages.flatMap((p) => p.items) ?? [], [claims.data]);

  const columns = useMemo<ColumnDef<ClaimSummary>[]>(
    () => [
      {
        id: "claim",
        header: t("claims.colClaim"),
        cell: ({ row }) => (
          <div className="whitespace-nowrap">
            <div className="tabular text-xs">{row.original.claim_number}</div>
            <div className="text-xs text-fg-2">{formatDateTime(row.original.requested_at, timezone)}</div>
          </div>
        ),
      },
      {
        id: "member",
        header: t("claims.colMember"),
        cell: ({ row }) => (
          <div className="flex items-center gap-2.5">
            <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-[11px] font-semibold text-brand">
              {initials(row.original.member_display_name)}
            </span>
            {row.original.member_display_name}
          </div>
        ),
      },
      { id: "provider", header: t("claims.colProvider"), cell: ({ row }) => <span className="text-fg-2">{row.original.provider_name}</span> },
      {
        id: "total",
        header: t("claims.colTotal"),
        meta: { align: "right" } satisfies ColumnMeta,
        cell: ({ row }) => formatMoney(row.original.total_xof, { unit: false }),
      },
      {
        id: "covered",
        header: t("claims.colCovered"),
        meta: { align: "right" } satisfies ColumnMeta,
        cell: ({ row }) => formatMoney(row.original.covered_xof, { unit: false }),
      },
      { id: "risk", header: t("claims.colRisk"), cell: ({ row }) => <RiskCell score={row.original.fraud_score} /> },
      {
        id: "status",
        header: t("claims.colStatus"),
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1.5">
            <ClaimStatusBadge status={row.original.status} />
            {row.original.fraud_flagged ? <FraudBadge /> : null}
          </div>
        ),
      },
    ],
    [timezone],
  );

  return (
    <>
      <PageHeader eyebrow={t("claims.eyebrow")} title={t("claims.title")} />
      <div role="group" aria-label={t("claims.filtersLabel")} className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <Toggle key={f.key} pressed={state.active === f.key} onPressedChange={() => state.setFilter(f.key)}>
            {t(f.label)}
          </Toggle>
        ))}
      </div>
      <Panel>
        {claims.isPending ? <LoadingRows /> : null}
        {claims.isError ? (
          <div className="p-4">
            <ErrorState error={claims.error} onRetry={() => void claims.refetch()} />
          </div>
        ) : null}
        {claims.isSuccess && rows.length === 0 ? (
          <EmptyState
            title={t("claims.emptyTitle")}
            body={t("claims.emptyBody")}
            next={t(state.active === "all" ? "emptyNext.claimsAll" : state.active === "en_revue" ? "emptyNext.claimsReview" : "emptyNext.claimsFilter")}
            action={
              state.active === "all" ? (
                <OpenPaletteButton />
              ) : (
                <>
                  <Button variant="outline" size="sm" onClick={() => state.setFilter("all")}>
                    {t("emptyNext.showAllClaims")}
                  </Button>
                  <OpenPaletteButton />
                </>
              )
            }
          />
        ) : null}
        {rows.length > 0 ? (
          <DataTable
            data={rows}
            columns={columns}
            label={t("claims.tableLabel")}
            getRowId={(c) => c.id}
            rowLabel={(c) => t("claims.openClaim", { number: c.claim_number })}
            onRowOpen={(c) => state.openClaim(c.id)}
          />
        ) : null}
        {claims.hasNextPage ? (
          <div className="border-t border-line p-3">
            <Button variant="outline" size="sm" onClick={() => void claims.fetchNextPage()} disabled={claims.isFetchingNextPage}>
              {t("common.loadMore")}
            </Button>
          </div>
        ) : null}
      </Panel>
      {state.claimId ? <ClaimDrawer claimId={state.claimId} onClose={() => state.openClaim(null)} /> : null}
    </>
  );
}
