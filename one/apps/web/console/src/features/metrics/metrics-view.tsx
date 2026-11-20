"use client";

import { CheckIcon, LockIcon, XIcon } from "lucide-react";
import { useState } from "react";
import { useAccess, useProductMetrics } from "@/api/queries";
import type { ProductMetric } from "@/api/types";
import { RequireRole } from "@/components/require-role";
import { EmptyState, ErrorState, LoadingRows, PageHeader, Panel } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/misc";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { t, tDynamic } from "@/i18n";
import { formatDate, formatDateTime } from "@/lib/format";
import { formatMetricValue, periodOf, targetMet } from "./format-metric";

const PERIODS = [7, 30, 90] as const;
type Period = (typeof PERIODS)[number];

export function MetricsView() {
  return (
    <RequireRole roles={["gestionnaire", "admin"]}>
      <MetricsContent />
    </RequireRole>
  );
}

function MetricRow({ metric, k }: { metric: ProductMetric; k: number }) {
  const value = formatMetricValue(metric);
  const met = targetMet(metric);
  const hasTarget = metric.key === "counter_decision_display_median_ms" || metric.key === "ledger_balance_gap_xof" || metric.key === "webhook_duplicate_rate";
  return (
    <TableRow data-testid="metric" data-key={metric.key} data-status={metric.status}>
      <TableCell>
        <div className="font-medium">{tDynamic("metrics.key", metric.key)}</div>
        <div className="text-caption text-fg-2">{tDynamic("metrics.desc", metric.key)}</div>
      </TableCell>
      <TableCell className="text-right">
        {value !== null ? (
          <span className="tabular-nums font-semibold">{value}</span>
        ) : (
          <span className="inline-flex flex-col items-end gap-0.5">
            <Badge tone="neutral" dot={false}>
              <LockIcon aria-hidden />
              {t("metrics.masked")}
            </Badge>
            <span className="text-caption text-fg-2">{t("metrics.maskedHint", { k })}</span>
          </span>
        )}
      </TableCell>
      <TableCell className="tabular text-right">{metric.contributors ?? t("metrics.noTarget")}</TableCell>
      <TableCell>
        {hasTarget ? (
          <div className="flex flex-col items-start gap-1">
            <span className="text-caption">{tDynamic("metrics.target", metric.key)}</span>
            {met === null ? null : (
              <Badge tone={met ? "ok" : "crit"} dot={false}>
                {met ? <CheckIcon aria-hidden /> : <XIcon aria-hidden />}
                {t(met ? "metrics.targetMet" : "metrics.targetMissed")}
              </Badge>
            )}
          </div>
        ) : (
          <span className="text-fg-2">{t("metrics.noTarget")}</span>
        )}
      </TableCell>
    </TableRow>
  );
}

/**
 * Mesure (Phase 2) : indicateurs k-anonymes de l'organisation (operationId `getProductMetrics`).
 * États : chargement, erreur (code, Réessayer), vide (que faire ensuite), tout masqué (élargir la
 * période), indicateur masqué (moins de k contributeurs : ni valeur ni effectif).
 */
function MetricsContent() {
  const { timezone } = useAccess();
  const [days, setDays] = useState<Period>(30);
  const [now] = useState(() => new Date());
  const period = periodOf(days, now, timezone);
  const metrics = useProductMetrics(period.from, period.to);
  const data = metrics.data;
  const k = data?.k_anonymity_threshold ?? 5;
  const allMasked = data !== undefined && data.items.length > 0 && data.items.every((m) => m.status === "masque");

  return (
    <>
      <PageHeader eyebrow={t("metrics.eyebrow")} title={t("metrics.title")}>
        <p className="m-0 max-w-[80ch] text-fg-2">{t("metrics.intro", { k })}</p>
      </PageHeader>
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label={t("metrics.periodLabel")} className="flex flex-wrap gap-1.5">
          {PERIODS.map((p) => (
            <Toggle key={p} pressed={days === p} onPressedChange={() => setDays(p)}>
              {tDynamic("metrics.period", String(p))}
            </Toggle>
          ))}
        </div>
        <span className="text-caption text-fg-2" data-testid="metrics-range">
          {t("metrics.periodRange", { from: formatDate(period.from), to: formatDate(period.to) })}
        </span>
      </div>
      <Panel>
        {metrics.isPending ? <LoadingRows rows={6} /> : null}
        {metrics.isError ? (
          <div className="p-4">
            <ErrorState error={metrics.error} onRetry={() => void metrics.refetch()} />
          </div>
        ) : null}
        {data && data.items.length === 0 ? <EmptyState title={t("metrics.emptyTitle")} body={t("metrics.emptyBody")} next={t("metrics.emptyNext")} /> : null}
        {allMasked ? (
          <div role="status" data-testid="metrics-all-masked" className="m-4 flex flex-wrap items-center gap-3 rounded-md border border-line bg-sunk p-3">
            <LockIcon className="size-4 text-fg-2" aria-hidden />
            <div className="flex-1">
              <p className="font-semibold">{t("metrics.allMaskedTitle")}</p>
              <p className="text-fg-2">{t("metrics.allMaskedBody", { k })}</p>
            </div>
            {days !== 90 ? (
              <Button variant="outline" size="sm" onClick={() => setDays(90)}>
                {t("metrics.widen")}
              </Button>
            ) : null}
          </div>
        ) : null}
        {data && data.items.length > 0 ? (
          <Table aria-label={t("metrics.tableLabel")}>
            <TableHeader>
              <TableRow>
                <TableHead>{t("metrics.colMetric")}</TableHead>
                <TableHead className="text-right">{t("metrics.colValue")}</TableHead>
                <TableHead className="text-right">{t("metrics.colContributors")}</TableHead>
                <TableHead>{t("metrics.colTarget")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((m) => (
                <MetricRow key={m.key} metric={m} k={k} />
              ))}
            </TableBody>
          </Table>
        ) : null}
        {data ? <p className="border-t border-line px-4 py-2.5 text-caption text-fg-2">{t("metrics.generatedAt", { date: formatDateTime(data.generated_at, timezone) })}</p> : null}
      </Panel>
      <p className="text-caption text-fg-2">{t("metrics.measureWhere")}</p>
    </>
  );
}
