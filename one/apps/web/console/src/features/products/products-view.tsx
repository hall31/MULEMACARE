"use client";

import { useEffect, useMemo, useState } from "react";
import { usePlans } from "@/api/queries";
import type { Plan, PlanVersion } from "@/api/types";
import { RequireRole } from "@/components/require-role";
import { EmptyState, ErrorState, LoadingRows, PageHeader, Panel } from "@/components/states";
import { PlanVersionBadge } from "@/components/status-badges";
import { Toggle } from "@/components/ui/misc";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { t, tDynamic, type MessageKey } from "@/i18n";
import { cn } from "@/lib/cn";
import { formatBasisPoints, formatDate, formatMoney } from "@/lib/format";

/** Produits et versions en lecture (R3 côté interface) : date d'effet, paramètres, écart avec la version précédente. */
export function ProductsView() {
  return (
    <RequireRole roles={["gestionnaire", "admin"]}>
      <ProductsContent />
    </RequireRole>
  );
}

function ProductsContent() {
  const plans = usePlans();
  const items = plans.data?.items ?? [];
  const [planId, setPlanId] = useState<string | null>(null);
  const plan = items.find((p) => p.id === planId) ?? items[0];

  return (
    <>
      <PageHeader eyebrow={t("products.eyebrow", { count: items.length })} title={t("products.title")}>
        <p className="m-0 max-w-[65ch] text-fg-2">{t("products.intro")}</p>
      </PageHeader>
      {plans.isPending ? <LoadingRows /> : null}
      {plans.isError ? <ErrorState error={plans.error} onRetry={() => void plans.refetch()} /> : null}
      {plans.isSuccess && items.length === 0 ? (
        <Panel>
          <EmptyState title={t("products.emptyTitle")} body={t("products.emptyBody")} next={t("emptyNext.productsEmpty")} />
        </Panel>
      ) : null}
      {items.length > 1 ? (
        <div role="group" aria-label={t("products.plansLabel")} className="flex flex-wrap gap-1.5">
          {items.map((p) => (
            <Toggle key={p.id} pressed={plan?.id === p.id} onPressedChange={() => setPlanId(p.id)}>
              {p.name}
            </Toggle>
          ))}
        </div>
      ) : null}
      {plan ? <PlanDetail key={plan.id} plan={plan} /> : null}
    </>
  );
}

function PlanDetail({ plan }: { plan: Plan }) {
  const versions = useMemo(() => [...plan.versions].sort((a, b) => a.version - b.version), [plan.versions]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => setSelectedId(null), [plan.id]);
  const current = versions.find((v) => v.id === (selectedId ?? plan.current_version_id)) ?? versions.at(-1);
  if (!current) return null;
  const previous = versions.filter((v) => v.version < current.version).at(-1);

  return (
    <>
      <h2 className="text-[20px] font-semibold">
        {plan.name} <span className="tabular text-[13px] font-normal text-fg-2">{plan.code}</span>
      </h2>
      <div role="group" aria-label={t("products.versionsLabel", { name: plan.name })} className="flex flex-wrap gap-2.5">
        {versions.map((v) => (
          <button
            key={v.id}
            type="button"
            aria-pressed={v.id === current.id}
            onClick={() => setSelectedId(v.id)}
            className={cn(
              "flex min-w-44 flex-1 flex-col gap-1 rounded-md border border-line bg-surface p-3 text-left hover:bg-sunk",
              v.id === current.id && "border-brand shadow-[inset_0_0_0_1px_var(--accent)]",
            )}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="tabular font-semibold">{t("common.version", { version: v.version })}</span>
              <PlanVersionBadge state={v.state} />
            </span>
            <span className="text-xs text-fg-2">
              {t("products.validity", { from: formatDate(v.valid_from), to: v.valid_to ? formatDate(v.valid_to) : t("products.openEnded") })}
            </span>
          </button>
        ))}
      </div>
      <Panel>
        <ParamsTable version={current} previous={previous} />
      </Panel>
      <Panel aria-labelledby="coverages-title">
        <div className="border-b border-line px-4 py-3">
          <h3 id="coverages-title" className="text-[15px] font-semibold">
            {t("products.coveragesTitle")}
          </h3>
        </div>
        <Table aria-labelledby="coverages-title">
          <TableHeader>
            <TableRow>
              <TableHead>{t("products.colCoverage")}</TableHead>
              <TableHead className="text-right">{t("products.colRate")}</TableHead>
              <TableHead className="text-right">{t("products.colLimit")}</TableHead>
              <TableHead>{t("products.colScope")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {current.coverages.map((c) => (
              <TableRow key={c.category}>
                <TableCell>{c.label}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {c.coverage_rate_bp === null || c.coverage_rate_bp === undefined ? (
                    <span className="text-fg-2">{t("products.rateOfVersion")}</span>
                  ) : (
                    t("products.percent", { value: formatBasisPoints(c.coverage_rate_bp) })
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {c.annual_limit_xof === null || c.annual_limit_xof === undefined ? (
                    <span className="text-fg-2">{t("products.noLimit")}</span>
                  ) : (
                    formatMoney(c.annual_limit_xof)
                  )}
                </TableCell>
                <TableCell>{tDynamic("products.scope", c.limit_scope)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>
    </>
  );
}

interface Param {
  key: keyof Pick<PlanVersion, "coverage_rate_bp" | "family_annual_ceiling_xof" | "waiting_period_days" | "monthly_contribution_xof">;
  label: MessageKey;
  format: (v: number) => string;
  /** Sens favorable à l'adhérent : une hausse du plafond est favorable, une hausse de la carence ne l'est pas. */
  higherIsBetter: boolean;
}

const PARAMS: Param[] = [
  { key: "coverage_rate_bp", label: "products.coverageRate", format: (v) => t("products.percent", { value: formatBasisPoints(v) }), higherIsBetter: true },
  { key: "family_annual_ceiling_xof", label: "products.ceiling", format: (v) => formatMoney(v), higherIsBetter: true },
  { key: "waiting_period_days", label: "products.waiting", format: (v) => t("products.days", { count: v }), higherIsBetter: false },
  { key: "monthly_contribution_xof", label: "products.monthly", format: (v) => formatMoney(v), higherIsBetter: false },
];

function ParamsTable({ version, previous }: { version: PlanVersion; previous: PlanVersion | undefined }) {
  return (
    <Table aria-label={t("products.paramsLabel", { version: version.version })}>
      <TableHeader>
        <TableRow>
          <TableHead>{t("products.colParam")}</TableHead>
          <TableHead className="text-right">{t("products.colValue")}</TableHead>
          <TableHead>{previous ? t("products.colDiff", { version: previous.version }) : t("products.noPrevious")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {PARAMS.map((p) => {
          const value = version[p.key];
          const diff = previous ? value - previous[p.key] : 0;
          const favourable = p.higherIsBetter ? diff > 0 : diff < 0;
          const sign = diff > 0 ? "+" : diff < 0 ? "−" : "";
          return (
            <TableRow key={p.key}>
              <TableCell>{t(p.label)}</TableCell>
              <TableCell className="text-right tabular-nums">{p.format(value)}</TableCell>
              <TableCell>
                {!previous ? null : diff === 0 ? (
                  <span className="text-xs text-fg-2">{t("products.unchanged")}</span>
                ) : (
                  <span className={cn("tabular text-xs", favourable ? "text-ok" : "text-crit")}>
                    {sign}
                    {p.format(Math.abs(diff))}
                  </span>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
