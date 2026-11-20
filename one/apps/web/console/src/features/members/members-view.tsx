"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { SearchIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useMembers, usePlans } from "@/api/queries";
import type { MemberStatus, MemberSummary } from "@/api/types";
import { DataTable } from "@/components/data-table";
import { RequireRole } from "@/components/require-role";
import { EmptyState, ErrorState, LoadingRows, PageHeader, Panel } from "@/components/states";
import { MemberStatusBadge } from "@/components/status-badges";
import { Button } from "@/components/ui/button";
import { Input, Toggle } from "@/components/ui/misc";
import { t, tDynamic } from "@/i18n";
import { initials } from "@/lib/format";
import { MemberDrawer } from "./member-drawer";

const STATUSES: readonly MemberStatus[] = ["actif", "carence", "suspendu"];

export function MembersView() {
  return (
    <RequireRole roles={["gestionnaire", "admin"]}>
      <MembersContent />
    </RequireRole>
  );
}

function MembersContent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const status = STATUSES.find((s) => s === params.get("statut"));
  const memberId = params.get("adherent");
  const [search, setSearch] = useState(params.get("q") ?? "");
  const deferred = useDeferredValue(search.trim());
  // Le contrat exige au moins 2 caractères (q, minLength 2).
  const q = deferred.length >= 2 ? deferred : undefined;

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  useEffect(() => {
    if ((params.get("q") ?? undefined) !== q) update({ q: q ?? null });
    // Synchronise seulement la recherche différée dans l'URL (partage du lien).
  }, [q]);

  const members = useMembers({ status, q });
  const plans = usePlans();
  const planName = useMemo(() => new Map(plans.data?.items.map((p) => [p.code, p.name]) ?? []), [plans.data]);
  const rows = useMemo(() => members.data?.pages.flatMap((p) => p.items) ?? [], [members.data]);

  const columns = useMemo<ColumnDef<MemberSummary>[]>(
    () => [
      {
        id: "member",
        header: t("members.colMember"),
        cell: ({ row }) => {
          const name = `${row.original.given_name} ${row.original.family_name}`;
          return (
            <div className="flex items-center gap-2.5">
              <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-soft text-[11px] font-semibold text-brand">
                {initials(name)}
              </span>
              <div>
                <div>{name}</div>
                <div className="tabular text-xs text-fg-2">{row.original.member_number}</div>
              </div>
            </div>
          );
        },
      },
      {
        id: "plan",
        header: t("members.colPlan"),
        cell: ({ row }) => planName.get(row.original.plan_code) ?? row.original.plan_code,
      },
      { id: "status", header: t("members.colStatus"), cell: ({ row }) => <MemberStatusBadge status={row.original.status} /> },
    ],
    [planName],
  );

  return (
    <>
      <PageHeader eyebrow={t("members.eyebrow")} title={t("members.title")} />
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-sm">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-fg-2" aria-hidden />
          <label htmlFor="member-search" className="sr-only">
            {t("members.searchLabel")}
          </label>
          <Input
            id="member-search"
            type="search"
            className="pl-8"
            value={search}
            placeholder={t("members.searchPlaceholder")}
            onChange={(e) => setSearch(e.target.value)}
            autoComplete="off"
          />
        </div>
        <div role="group" aria-label={t("members.filtersLabel")} className="flex flex-wrap gap-1.5">
          <Toggle pressed={!status} onPressedChange={() => update({ statut: null })}>
            {t("members.filterAll")}
          </Toggle>
          {STATUSES.map((s) => (
            <Toggle key={s} pressed={status === s} onPressedChange={() => update({ statut: s })}>
              {tDynamic("memberStatus", s)}
            </Toggle>
          ))}
        </div>
      </div>
      <Panel>
        {members.isPending ? <LoadingRows /> : null}
        {members.isError ? (
          <div className="p-4">
            <ErrorState error={members.error} onRetry={() => void members.refetch()} />
          </div>
        ) : null}
        {members.isSuccess && rows.length === 0 ? (
          <EmptyState
            title={t("members.emptyTitle")}
            body={t("members.emptyBody")}
            next={t(q ? "emptyNext.membersSearch" : "emptyNext.membersFilter")}
            action={
              q ? (
                <Button variant="outline" size="sm" onClick={() => setSearch("")}>
                  {t("emptyNext.clearSearch")}
                </Button>
              ) : status ? (
                <Button variant="outline" size="sm" onClick={() => update({ statut: null })}>
                  {t("emptyNext.showAllMembers")}
                </Button>
              ) : undefined
            }
          />
        ) : null}
        {rows.length > 0 ? (
          <DataTable
            data={rows}
            columns={columns}
            label={t("members.tableLabel")}
            getRowId={(m) => m.id}
            rowLabel={(m) => t("members.openMember", { name: `${m.given_name} ${m.family_name}`, number: m.member_number })}
            onRowOpen={(m) => update({ adherent: m.id })}
          />
        ) : null}
        {members.hasNextPage ? (
          <div className="border-t border-line p-3">
            <Button variant="outline" size="sm" onClick={() => void members.fetchNextPage()} disabled={members.isFetchingNextPage}>
              {t("common.loadMore")}
            </Button>
          </div>
        ) : null}
      </Panel>
      {memberId ? <MemberDrawer memberId={memberId} planName={planName} onClose={() => update({ adherent: null })} /> : null}
    </>
  );
}
