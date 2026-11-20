"use client";

import { useState } from "react";
import { useAccess, useEmployerConsumption, useEmployerContracts } from "@/api/queries";
import type { EmployerContract, EmployerContractStatus, EmployerGroupConsumption } from "@/api/types";
import { BarChart, type BarRow } from "@/components/bar-chart";
import { KTier, KValue, KpiCard } from "@/components/kvalue";
import { PeriodPicker, type PeriodWeeks } from "@/components/period-picker";
import { RequireRole } from "@/components/shell";
import { EmptyState, ErrorState, Loading } from "@/components/states";
import { Badge, Icon, PageHeader, Panel, ScrollRegion, type Tone } from "@/components/ui";
import { t, tDynamic } from "@/i18n";
import { formatDate, formatMoneyApprox, weeksPeriod } from "@/lib/format";
import { countLabel, isAvailable } from "@/lib/kanon";
import { MEMBER_STATUS_TONE } from "../insurer/portfolio-view";
import { categoryLabel } from "../labels";

/** Échéance d'un contrat de groupe : sémantique du contrat (§5), jamais l'accent. */
export const CONTRACT_STATUS_TONE: Record<EmployerContractStatus, Tone> = { en_cours: "ok", a_echeance: "warn", echu: "crit", sans_echeance: "neutral" };
const HORIZONS = [30, 90, 180, 365] as const;

export function EmployerView() {
  const { organization } = useAccess();
  // Titre rendu tout de suite (rendu serveur, LCP) ; les données attendent la session et le rôle.
  return (
    <>
      <PageHeader eyebrow={t("employer.eyebrow", { name: organization?.name ?? t("app.name") })} title={t("employer.title")}>
        <p className="max-w-[80ch] text-fg-2">{t("employer.intro")}</p>
      </PageHeader>
      <RequireRole roles={["employeur"]}>
        <EmployerContent />
      </RequireRole>
    </>
  );
}

/**
 * Espace employeur (P3, `getEmployerConsumption`, `listEmployerContracts`) : consommation agrégée
 * et anonymisée de chaque groupe de la portée du jeton, contrats arrivant à échéance. Aucun nom de
 * salarié, aucun dossier ; une valeur portée par moins de 5 personnes est « Masqué ».
 */
function EmployerContent() {
  const { timezone } = useAccess();
  const [weeks, setWeeks] = useState<PeriodWeeks>(4);
  const [now] = useState(() => new Date());
  const period = weeksPeriod(weeks, now, timezone);
  const consumption = useEmployerConsumption(period.from, period.to);
  return (
    <>
      <Contracts />
      <section aria-labelledby="consumption-title" className="flex flex-col gap-4">
        <h2 id="consumption-title" className="text-title">
          {t("employer.consumptionTitle")}
        </h2>
        <PeriodPicker weeks={weeks} onChange={setWeeks} from={period.from} to={period.to} />
        {consumption.isPending ? (
          <Panel>
            <Loading rows={5} />
          </Panel>
        ) : null}
        {consumption.isError ? <ErrorState error={consumption.error} onRetry={() => void consumption.refetch()} /> : null}
        {consumption.data && consumption.data.groups.length === 0 ? (
          <Panel>
            <EmptyState title={t("employer.noGroupTitle")} body={t("employer.noGroupBody")} />
          </Panel>
        ) : null}
        {consumption.data ? (
          <p className="text-dense" data-testid="published-period">
            {t("period.published", { from: formatDate(consumption.data.period_from), to: formatDate(consumption.data.period_to) })}
          </p>
        ) : null}
        {consumption.data?.groups.map((group) => <GroupPanel key={group.employer_id} group={group} k={consumption.data.k_anonymity_threshold} />)}
      </section>
    </>
  );
}

function GroupPanel({ group, k }: { group: EmployerGroupConsumption; k: number }) {
  const money = (v: number) => formatMoneyApprox(v);
  const count = (v: number) => countLabel(v);
  const headingId = `groupe-${group.employer_id}`;
  const allMasked = !isAvailable(group.claims) && group.members_by_status.every((s) => !isAvailable(s.count));
  const statusRows: BarRow[] = group.members_by_status.map((s) => ({
    key: s.status,
    label: tDynamic("memberStatus", s.status),
    value: s.count,
    tone: MEMBER_STATUS_TONE[s.status],
    status: s.status,
    columns: [{ label: t("insurer.membersCol"), value: s.count, format: count }],
  }));
  const categoryRows: BarRow[] = group.benefits_by_category.map((c) => ({
    key: c.category,
    label: categoryLabel(c.category),
    value: c.covered_xof,
    tone: "neutral",
    columns: [
      { label: t("insurer.coveredCol"), value: c.covered_xof, format: money },
      { label: t("insurer.claimsCol"), value: c.claims, format: count },
    ],
  }));
  return (
    <Panel aria-labelledby={headingId} className="flex flex-col gap-5 p-5" data-testid="employer-group">
      <h3 id={headingId} className="text-title">
        {group.name}
      </h3>
      {allMasked ? (
        <p role="note" className="flex items-start gap-2 rounded-md border border-line bg-sunk p-3" data-testid="group-masked">
          <Icon name="lock" className="mt-0.5 text-fg-2" />
          <span>{t("employer.smallGroup", { k })}</span>
        </p>
      ) : null}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard label={t("employer.members")} value={group.members_total} format={count} />
        <KpiCard label={t("employer.claims")} value={group.claims} format={count} />
        <KpiCard label={t("employer.covered")} value={group.covered_xof} format={money} />
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <BarChart id={`statuts-${group.employer_id}`} title={t("insurer.byStatus")} rows={statusRows} format={count} level={4} />
        {categoryRows.length > 0 ? (
          <BarChart id={`categories-${group.employer_id}`} title={t("insurer.byCategory")} caption={t("insurer.byCategoryCaption")} rows={categoryRows} format={money} level={4} />
        ) : (
          <div className="flex flex-col gap-2">
            <h4 className="font-display text-body font-semibold">{t("insurer.byCategory")}</h4>
            <p className="text-fg-2" data-testid="categories-none">
              {t("employer.noCategory", { k })}
            </p>
          </div>
        )}
      </div>
    </Panel>
  );
}

function Contracts() {
  const [within, setWithin] = useState<(typeof HORIZONS)[number]>(90);
  const contracts = useEmployerContracts(within);
  const items = contracts.data?.items ?? [];
  const order: Record<EmployerContractStatus, number> = { echu: 0, a_echeance: 1, en_cours: 2, sans_echeance: 3 };
  const sorted = [...items].sort((a, b) => order[a.status] - order[b.status] || (a.days_remaining ?? 99_999) - (b.days_remaining ?? 99_999));
  const dueCount = items.filter((c) => c.status === "a_echeance").length;
  return (
    <Panel aria-labelledby="contracts-title" data-testid="contracts">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line p-5">
        <div className="flex flex-col gap-1">
          <h2 id="contracts-title" className="text-title">
            {t("employer.contractsTitle")}
          </h2>
          <p className="text-fg-2" data-testid="contracts-summary">
            {contracts.data ? t("employer.contractsSummary", { count: dueCount, days: within }) : t("employer.contractsIntro")}
          </p>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="within-days" className="text-caption font-medium text-fg-2">
            {t("employer.horizon")}
          </label>
          <select id="within-days" value={within} onChange={(e) => setWithin(Number(e.target.value) as (typeof HORIZONS)[number])} className="min-h-12 rounded-md border border-line-2 bg-surface px-3">
            {HORIZONS.map((h) => (
              <option key={h} value={h}>
                {t("employer.horizonOption", { days: h })}
              </option>
            ))}
          </select>
        </div>
      </div>
      {contracts.isPending ? <Loading rows={3} /> : null}
      {contracts.isError ? (
        <div className="p-5">
          <ErrorState error={contracts.error} onRetry={() => void contracts.refetch()} />
        </div>
      ) : null}
      {contracts.data && items.length === 0 ? <EmptyState title={t("employer.noContractTitle")} body={t("employer.noContractBody")} /> : null}
      {items.length > 0 ? (
        <ScrollRegion label={t("employer.contractsTitle")}>
          <table className="w-full min-w-[640px] border-collapse">
            <thead>
              <tr className="border-b border-line text-left text-fg-2">
                <th scope="col" className="px-5 py-2 font-medium">
                  {t("employer.groupCol")}
                </th>
                <th scope="col" className="px-5 py-2 font-medium">
                  {t("employer.endCol")}
                </th>
                <th scope="col" className="px-5 py-2 font-medium">
                  {t("employer.statusCol")}
                </th>
                <th scope="col" className="px-5 py-2 text-right font-medium">
                  {t("employer.membersCol")}
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((c) => (
                <ContractRow key={c.employer_id} contract={c} />
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      ) : null}
    </Panel>
  );
}

function remaining(c: EmployerContract): string {
  if (c.days_remaining === null) return t("employer.noEnd");
  if (c.days_remaining < 0) return t("employer.endedAgo", { days: -c.days_remaining });
  if (c.days_remaining === 0) return t("employer.endsToday");
  return t("employer.endsIn", { days: c.days_remaining });
}

function ContractRow({ contract: c }: { contract: EmployerContract }) {
  return (
    <tr className="border-b border-line last:border-b-0" data-testid="contract-row" data-status={c.status}>
      <th scope="row" className="px-5 py-3 text-left font-medium">
        {c.name}
        <span className="block text-caption font-normal text-fg-2">{t("employer.since", { date: formatDate(c.contract_start) })}</span>
      </th>
      <td className="px-5 py-3">
        <span className="num">{c.contract_end ? formatDate(c.contract_end) : t("employer.noEndShort")}</span>
        <span className="block text-caption text-fg-2">{remaining(c)}</span>
      </td>
      <td className="px-5 py-3">
        <Badge tone={CONTRACT_STATUS_TONE[c.status]}>{tDynamic("contractStatus", c.status)}</Badge>
      </td>
      <td className="px-5 py-3 text-right">
        <KValue value={c.members_total} format={countLabel} />
        <KTier value={c.members_total} className="block" />
      </td>
    </tr>
  );
}
