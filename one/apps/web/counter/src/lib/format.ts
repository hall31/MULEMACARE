import { t } from "@/i18n";

function formatXofNumber(amount: number): string {
  if (!Number.isSafeInteger(amount)) throw new Error("Montant FCFA non entier");
  // Espace insécable fine en séparateur de milliers (usage fr-FR).
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(amount);
}

/** Montants en entiers FCFA : jamais de décimales ni de flottants. */
export function formatXof(amount: number): string {
  return t("money.xof", { amount: formatXofNumber(amount) });
}

/**
 * Le même texte que `formatXof`, découpé autour du nombre pour styler l'unité à part
 * (montant héros : chiffres 40 px, unité 20 px). `before + number + after === formatXof(amount)`.
 */
export function formatXofParts(amount: number): { before: string; number: string; after: string } {
  const [before = "", after = ""] = t("money.xof").split("{amount}");
  return { before, number: formatXofNumber(amount), after };
}

/** Taux en points de base (8000 = 80 %). */
export function formatRateBp(bp: number): string {
  const value = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(bp / 100);
  return t("percent", { value });
}

/** Heure locale de l'instance (Africa/Abidjan, Africa/Dakar), stockage en UTC. */
export function formatTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone }).format(new Date(iso));
}

/** Date du soin (AAAA-MM-JJ) dans le fuseau de l'instance. */
export function localDate(now: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export function initials(displayName: string): string {
  return displayName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w.charAt(0).toUpperCase())
    .join("");
}
