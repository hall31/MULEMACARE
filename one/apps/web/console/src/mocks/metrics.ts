/**
 * Indicateurs produit simulés (getProductMetrics, x-lot P2), CALCULÉS sur l'état de démonstration
 * comme le fait apps/api/metrics : dossiers, grand livre, événements d'usage reçus. Un indicateur
 * porté par moins de 5 contributeurs est masqué (ni valeur ni effectif). Aucun chiffre saisi.
 */
import type { ProductMetric, ProductMetrics } from "@/api/types";
import { demoState } from "./store";

export const K_ANONYMITY = 5;
const DAY_MS = 86_400_000;

function day(offset: number): string {
  return new Date(Date.now() + offset * DAY_MS).toISOString().slice(0, 10);
}

function metric(key: ProductMetric["key"], unit: ProductMetric["unit"], value: number | null, contributors: number): ProductMetric {
  return contributors >= K_ANONYMITY && value !== null
    ? { key, unit, status: "disponible", value: Math.round(value), contributors }
    : { key, unit, status: "masque", value: null, contributors: null };
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor((sorted.length - 1) / 2)] ?? null;
}

export function productMetrics(from: string | null, to: string | null): ProductMetrics {
  const periodFrom = from ?? day(-29);
  const periodTo = to ?? day(0);
  const inPeriod = (date: string) => date >= periodFrom && date <= periodTo;
  const claims = demoState().claims.filter((d) => inPeriod(d.claim.service_date));
  const beneficiaries = new Set(claims.map((d) => d.claim.member_id)).size;
  const first = claims.map((d) => d.decisions[0]).filter((d) => d !== undefined);
  const rate = (n: number, total: number) => (total === 0 ? null : (n * 10_000) / total);
  const definitive = claims
    .map((d) => d.decisions.find((x) => x.outcome === "accordee_auto" || x.outcome === "accordee" || x.outcome === "refusee"))
    .map((d, i) => (d ? Date.parse(d.decided_at) - Date.parse(claims[i]!.claim.requested_at) : null))
    .filter((v): v is number => v !== null);
  const entries = demoState().ledger.filter((e) => inPeriod(e.accounting_date));
  const lines = entries.flatMap((e) => e.lines);
  const events = demoState().productEvents;
  const sessions = (name: string) => new Set(events.filter((e) => e.name === name).map((e) => e.session_id)).size;
  const counterDurations = events.filter((e) => e.name === "counter_decision_shown" && e.duration_ms !== undefined).map((e) => e.duration_ms ?? 0);
  const started = sessions("onboarding_started");

  return {
    period_from: periodFrom,
    period_to: periodTo,
    generated_at: new Date().toISOString(),
    k_anonymity_threshold: K_ANONYMITY,
    items: [
      metric("claims_auto_approved_rate", "pour_dix_mille", rate(first.filter((d) => d.outcome === "accordee_auto").length, first.length), beneficiaries),
      metric("claims_review_rate", "pour_dix_mille", rate(first.filter((d) => d.outcome === "en_revue").length, first.length), beneficiaries),
      metric("claims_decision_median_ms", "millisecondes", median(definitive), beneficiaries),
      metric("counter_decision_display_median_ms", "millisecondes", median(counterDurations), sessions("counter_decision_shown")),
      metric("onboarding_completion_rate", "pour_dix_mille", rate(sessions("onboarding_completed"), started), started),
      metric("first_card_median_ms", "millisecondes", null, sessions("card_presented")),
      metric("payment_links_paid_rate", "pour_dix_mille", null, 0),
      metric("ledger_balance_gap_xof", "xof", lines.reduce((s, l) => s + l.debit_xof - l.credit_xof, 0), entries.length),
      metric("webhook_duplicate_rate", "pour_dix_mille", null, 0),
    ],
  };
}
