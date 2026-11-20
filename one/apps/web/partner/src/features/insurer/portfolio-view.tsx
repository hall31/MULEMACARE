"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/api/client";
import { useAccess, useExportPortfolio, useInsurerPortfolio } from "@/api/queries";
import type { InsurerPortfolio, MemberStatus } from "@/api/types";
import { BarChart, type BarRow } from "@/components/bar-chart";
import { KTier, KValue, KpiCard } from "@/components/kvalue";
import { PeriodPicker, type PeriodWeeks } from "@/components/period-picker";
import { RequireRole } from "@/components/shell";
import { EmptyState, ErrorState, Loading } from "@/components/states";
import { Button, Icon, PageHeader, Panel, ScrollRegion, type Tone } from "@/components/ui";
import { t, tDynamic } from "@/i18n";
import { formatBasisPoints, formatDate, formatDateTime, formatDuration, formatMoneyApprox, weeksPeriod } from "@/lib/format";
import { countLabel, isAvailable } from "@/lib/kanon";
import { categoryLabel } from "../labels";

/** Statuts d'adhérent : sémantique du contrat (§5), jamais l'accent. */
export const MEMBER_STATUS_TONE: Record<MemberStatus, Tone> = { actif: "ok", carence: "warn", suspendu: "crit" };

export function PortfolioView() {
  const { organization } = useAccess();
  // Titre rendu tout de suite (rendu serveur, LCP) ; les données attendent la session et le rôle.
  return (
    <>
      <PageHeader eyebrow={t("insurer.eyebrow", { name: organization?.name ?? t("app.name") })} title={t("insurer.title")}>
        <p className="max-w-[80ch] text-fg-2">{t("insurer.intro")}</p>
      </PageHeader>
      <RequireRole roles={["assureur", "admin"]}>
        <PortfolioContent />
      </RequireRole>
    </>
  );
}

/**
 * Espace assureur (P3, `getInsurerPortfolio`, `exportInsurerPortfolio`) : portefeuille agrégé de
 * l'organisation, lecture seule. k-anonymat : une valeur portée par moins de 5 personnes est
 * « Masqué » (ni valeur, ni effectif), l'effectif est écrit par palier (« 10 à 19 personnes »).
 * États : chargement, erreur (code, Réessayer), vide (aucun soin sur la période), tout masqué.
 */
function PortfolioContent() {
  const { timezone } = useAccess();
  const [weeks, setWeeks] = useState<PeriodWeeks>(4);
  const [now] = useState(() => new Date());
  const period = weeksPeriod(weeks, now, timezone);
  const portfolio = useInsurerPortfolio(period.from, period.to);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PeriodPicker weeks={weeks} onChange={setWeeks} from={period.from} to={period.to} />
        <ExportButton from={period.from} to={period.to} disabled={!portfolio.isSuccess} />
      </div>
      {portfolio.isPending ? (
        <Panel>
          <Loading rows={6} />
        </Panel>
      ) : null}
      {portfolio.isError ? <ErrorState error={portfolio.error} onRetry={() => void portfolio.refetch()} /> : null}
      {portfolio.data ? <Portfolio data={portfolio.data} timezone={timezone} widen={weeks < 13 ? () => setWeeks(13) : null} /> : null}
    </>
  );
}

function Portfolio({ data, timezone, widen }: { data: InsurerPortfolio; timezone: string; widen: (() => void) | null }) {
  const k = data.k_anonymity_threshold;
  const noCare = data.benefits_by_category.length === 0 && data.top_providers.length === 0 && !isAvailable(data.claims_cost_xof);
  const someMasked = [...data.members_by_status.map((s) => s.count), data.premiums_xof, data.claims_cost_xof, data.loss_ratio_bp, data.decision_delay_mean_ms, data.automation_rate_bp].some((v) => !isAvailable(v));
  const money = (v: number) => formatMoneyApprox(v);
  const count = (v: number) => countLabel(v);

  const statusRows: BarRow[] = data.members_by_status.map((s) => ({
    key: s.status,
    label: tDynamic("memberStatus", s.status),
    value: s.count,
    tone: MEMBER_STATUS_TONE[s.status],
    status: s.status,
    columns: [{ label: t("insurer.membersCol"), value: s.count, format: count }],
  }));
  const categoryRows: BarRow[] = data.benefits_by_category.map((c) => ({
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
    <div className="flex flex-col gap-6" data-testid="portfolio">
      <p className="text-dense" data-testid="published-period">
        {t("period.published", { from: formatDate(data.period_from), to: formatDate(data.period_to) })}
      </p>
      {someMasked ? (
        <div role="note" className="flex items-start gap-3 rounded-md border border-line bg-sunk p-4" data-testid="masked-note">
          <Icon name="lock" className="mt-0.5 text-fg-2" />
          <div className="flex-1">
            <p className="font-semibold">{t("kanon.noteTitle", { k })}</p>
            <p className="text-fg-2">{t("kanon.noteBody", { k })}</p>
          </div>
          {widen ? <Button onClick={widen}>{t("kanon.widen")}</Button> : null}
        </div>
      ) : null}

      <section aria-labelledby="kpi-title" className="flex flex-col gap-3">
        <h2 id="kpi-title" className="text-title">
          {t("insurer.kpiTitle")}
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <KpiCard testId="kpi-members" label={t("insurer.members")} value={data.members_total} format={count} />
          <KpiCard testId="kpi-loss-ratio" label={t("insurer.lossRatio")} value={data.loss_ratio_bp} format={formatBasisPoints} hint={t("insurer.lossRatioHint")} />
          <KpiCard testId="kpi-premiums" label={t("insurer.premiums")} value={data.premiums_xof} format={money} />
          <KpiCard testId="kpi-claims-cost" label={t("insurer.claimsCost")} value={data.claims_cost_xof} format={money} />
          <KpiCard testId="kpi-delay" label={t("insurer.decisionDelay")} value={data.decision_delay_mean_ms} format={formatDuration} />
          <KpiCard testId="kpi-automation" label={t("insurer.automation")} value={data.automation_rate_bp} format={formatBasisPoints} hint={t("insurer.automationHint")} />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel className="p-5">
          <BarChart id="statuts" title={t("insurer.byStatus")} caption={t("insurer.byStatusCaption")} rows={statusRows} format={count} />
        </Panel>
        <Panel className="p-5">
          {categoryRows.length > 0 ? (
            <BarChart id="categories" title={t("insurer.byCategory")} caption={t("insurer.byCategoryCaption")} rows={categoryRows} format={money} />
          ) : (
            <>
              <h3 className="text-body">{t("insurer.byCategory")}</h3>
              <EmptyState title={t("insurer.noCareTitle")} body={t("insurer.noCareBody")} />
            </>
          )}
        </Panel>
      </div>

      <Panel aria-labelledby="providers-title">
        <div className="flex flex-col gap-1 border-b border-line p-5">
          <h2 id="providers-title" className="text-title">
            {t("insurer.providers")}
          </h2>
          <p className="text-fg-2">{t("insurer.providersCaption")}</p>
        </div>
        {noCare || data.top_providers.length === 0 ? (
          <EmptyState title={t("insurer.noProviderTitle")} body={t("insurer.noProviderBody", { k })} />
        ) : (
          <ScrollRegion label={t("insurer.providers")}>
            <table className="w-full min-w-[560px] border-collapse">
              <thead>
                <tr className="border-b border-line text-left text-fg-2">
                  <th scope="col" className="px-5 py-2 font-medium">
                    {t("insurer.providerCol")}
                  </th>
                  <th scope="col" className="px-5 py-2 text-right font-medium">
                    {t("insurer.coveredCol")}
                  </th>
                  <th scope="col" className="px-5 py-2 text-right font-medium">
                    {t("insurer.claimsCol")}
                  </th>
                  <th scope="col" className="px-5 py-2 text-right font-medium">
                    {t("chart.tierCol")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.top_providers.map((p) => (
                  <tr key={p.provider_id} className="border-b border-line" data-testid="provider-row">
                    <th scope="row" className="px-5 py-2.5 text-left font-medium">
                      {p.name}
                    </th>
                    <td className="px-5 py-2.5 text-right">
                      <KValue value={p.covered_xof} format={money} />
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      <KValue value={p.claims} format={count} />
                    </td>
                    <td className="px-5 py-2.5 text-right">
                      <KTier value={p.covered_xof} />
                    </td>
                  </tr>
                ))}
                <tr data-testid="provider-others">
                  <th scope="row" className="px-5 py-2.5 text-left font-medium text-fg-2">
                    {t("insurer.otherProviders")}
                  </th>
                  <td className="px-5 py-2.5 text-right">
                    <KValue value={data.other_providers.covered_xof} format={money} />
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    <KValue value={data.other_providers.claims} format={count} />
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    <KTier value={data.other_providers.covered_xof} />
                  </td>
                </tr>
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </Panel>

      <p className="text-caption text-fg-2" data-testid="generated-at">
        {t("insurer.generated", { at: formatDateTime(data.generated_at, timezone), k })}
      </p>
    </div>
  );
}

/**
 * Export CSV agrégé (`exportInsurerPortfolio`) : mêmes agrégats, mêmes masques, aucune personne.
 * Le fichier est construit par l'API ; l'écran ne fait que le proposer au téléchargement.
 */
function ExportButton({ from, to, disabled }: { from: string; to: string; disabled: boolean }) {
  const exporter = useExportPortfolio();
  const [ready, setReady] = useState<string | null>(null);
  const linkRef = useRef<HTMLAnchorElement>(null);
  const filename = t("insurer.exportFilename", { from, to });

  useEffect(() => {
    if (!exporter.data) return;
    const url = URL.createObjectURL(new Blob([exporter.data], { type: "text/csv;charset=utf-8" }));
    setReady(url);
    return () => URL.revokeObjectURL(url);
  }, [exporter.data]);
  useEffect(() => {
    if (ready) linkRef.current?.click();
  }, [ready]);

  const problem = exporter.error instanceof ApiError ? exporter.error.problem : null;
  return (
    <div className="flex flex-col items-end gap-1.5">
      <Button variant="primary" onClick={() => exporter.mutate({ from, to })} disabled={disabled || exporter.isPending} aria-busy={exporter.isPending || undefined} data-testid="export-csv">
        <Icon name="download" />
        {t("insurer.export")}
      </Button>
      {ready ? (
        <a ref={linkRef} href={ready} download={filename} className="text-caption text-fg-2 underline underline-offset-2" data-testid="export-link">
          {t("insurer.exportReady", { file: filename })}
        </a>
      ) : null}
      {exporter.isError ? (
        <p role="alert" className="flex items-center gap-1.5 text-caption text-crit" data-testid="export-error">
          <Icon name="alert" className="size-3.5" />
          {problem ? t("insurer.exportError", { message: problem.message, code: problem.code }) : t("states.unknownError")}
        </p>
      ) : null}
      <span className="sr-only" aria-live="polite">
        {exporter.isPending ? t("insurer.exportPending") : ready ? t("insurer.exportReady", { file: filename }) : ""}
      </span>
    </div>
  );
}
