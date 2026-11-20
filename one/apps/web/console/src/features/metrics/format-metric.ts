import type { ProductMetric } from "@/api/types";
import { t } from "@/i18n";
import { formatBasisPoints, formatMoney } from "@/lib/format";

const decimal1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

/** Valeur lisible d'un indicateur disponible : taux en %, durées en s / min / h, écart en FCFA. */
export function formatMetricValue(metric: ProductMetric): string | null {
  if (metric.status !== "disponible" || metric.value === null) return null;
  const v = metric.value;
  if (metric.unit === "pour_dix_mille") return t("products.percent", { value: formatBasisPoints(v) });
  if (metric.unit === "xof") return formatMoney(v);
  if (v < 60_000) return t("metrics.seconds", { value: decimal1.format(v / 1000) });
  if (v < 3_600_000) return t("metrics.minutes", { value: decimal1.format(v / 60_000) });
  return t("metrics.hours", { value: decimal1.format(v / 3_600_000) });
}

/**
 * Objectifs écrits dans les contrats seulement (aucun seuil inventé) : décision au comptoir en
 * moins de 10 s (PRD objectif 1), grand livre équilibré, aucun doublon de cotisation.
 */
export const TARGETS: Partial<Record<ProductMetric["key"], (value: number) => boolean>> = {
  counter_decision_display_median_ms: (v) => v < 10_000,
  ledger_balance_gap_xof: (v) => v === 0,
  webhook_duplicate_rate: (v) => v === 0,
};

export function targetMet(metric: ProductMetric): boolean | null {
  const check = TARGETS[metric.key];
  if (!check || metric.status !== "disponible" || metric.value === null) return null;
  return check(metric.value);
}

/** Période de N jours se terminant aujourd'hui (jours locaux du fuseau de l'organisation). */
export function periodOf(days: number, now: Date, timeZone: string): { from: string; to: string } {
  const fmt = (d: Date) => new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  return { from: fmt(new Date(now.getTime() - (days - 1) * 86_400_000)), to: fmt(now) };
}
