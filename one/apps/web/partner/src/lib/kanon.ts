import type { KAnonymousValue } from "@/api/types";
import { t } from "@/i18n";

/**
 * k-anonymat affiché (CR-P3-01, Q-P3-11). Une valeur portée par moins de 5 personnes est
 * `masque` : ni valeur, ni effectif. Sinon l'effectif est publié par PALIER (plancher 5, 10, 20, 50,
 * 100) et affiché comme un intervalle (« 5 à 9 personnes »), jamais comme un nombre exact.
 */
export const TIERS = [5, 10, 20, 50, 100] as const;

export function isAvailable(value: KAnonymousValue): value is KAnonymousValue & { status: "disponible"; value: number } {
  return value.status === "disponible" && value.value !== null;
}

/** Intervalle du palier : 5 → « 5 à 9 personnes », 100 → « 100 personnes ou plus ». */
export function tierLabel(contributors: number | null): string | null {
  if (contributors === null) return null;
  const index = TIERS.indexOf(contributors as (typeof TIERS)[number]);
  const next = index >= 0 ? TIERS[index + 1] : undefined;
  if (next === undefined) return t("kanon.tierOpen", { from: contributors });
  return t("kanon.tierRange", { from: contributors, to: next - 1 });
}

/**
 * Compte publié (adhérents, dossiers) : depuis CR-P3-02 la valeur EST le plancher de son palier,
 * jamais un compte exact. Affiché comme une tranche : 10 → « 10 à 19 », 100 → « 100 ou plus ».
 */
export function countLabel(value: number): string {
  const index = TIERS.indexOf(value as (typeof TIERS)[number]);
  const next = index >= 0 ? TIERS[index + 1] : undefined;
  return next === undefined ? t("kanon.countOpen", { from: value }) : t("kanon.countRange", { from: value, to: next - 1 });
}

/** Plus grande valeur disponible d'une série (pour l'échelle des barres) ; 0 si tout est masqué. */
export function seriesMax(values: KAnonymousValue[]): number {
  return values.reduce((max, v) => (isAvailable(v) ? Math.max(max, v.value) : max), 0);
}
