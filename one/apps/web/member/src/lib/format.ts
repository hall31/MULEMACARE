import { t } from "@/i18n";

const intFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

function formatInt(amount: number): string {
  if (!Number.isSafeInteger(amount)) throw new Error("Montant non entier");
  // Espace insécable fine en séparateur de milliers (usage fr-FR).
  return intFormat.format(amount);
}

/** Montants en entiers FCFA : jamais de décimales ni de flottants. */
export function formatXof(amount: number): string {
  return t("money.xof", { amount: formatInt(amount) });
}

/** Le même texte que `formatXof`, découpé autour du nombre (montant héros : unité plus petite). */
export function formatXofParts(amount: number): { before: string; number: string; after: string } {
  const [before = "", after = ""] = t("money.xof").split("{amount}");
  return { before, number: formatInt(amount), after };
}

/** Taux en points de base (8000 = 80 %). */
export function formatRateBp(bp: number): string {
  const value = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(bp / 100);
  return t("percent", { value });
}

/** Part du plafond consommée, en pour cent entiers bornés à [0, 100] ; arrondi supérieur dès 1 franc. */
export function usedPercent(consumed: number, ceiling: number): number {
  if (ceiling <= 0 || consumed <= 0) return 0;
  if (consumed >= ceiling) return 100;
  return Math.min(99, Math.max(1, Math.round((consumed * 100) / ceiling)));
}

/**
 * Parité fixe du franc CFA (UEMOA) : 1 € = 655,957 FCFA, exprimée en millièmes pour rester en
 * entiers. Fait monétaire légal, pas une règle de la mutuelle : sert seulement à afficher un
 * équivalent indicatif au payeur de la diaspora (le contrat ne donne que le montant en FCFA).
 */
export const XOF_PER_EUR_MILLI = 655_957;

/** Équivalent en centimes d'euro, arrondi au centime le plus proche (demi vers le haut), en entiers. */
export function eurEquivalentCents(xof: number): number {
  if (!Number.isSafeInteger(xof) || xof < 0) throw new Error("Montant FCFA non entier");
  return Math.floor((xof * 100_000 * 2 + XOF_PER_EUR_MILLI) / (2 * XOF_PER_EUR_MILLI));
}

export function formatEurCents(cents: number): string {
  const euros = Math.floor(cents / 100);
  const rest = String(cents % 100).padStart(2, "0");
  return t("money.eur", { amount: `${formatInt(euros)},${rest}` });
}

export function formatParity(): string {
  const whole = Math.floor(XOF_PER_EUR_MILLI / 1000);
  const decimals = String(XOF_PER_EUR_MILLI % 1000).padStart(3, "0");
  return t("money.xof", { amount: `${formatInt(whole)},${decimals}` });
}

/* --------------------------- Dates : UTC en base, heure locale à l'affichage --------------------------- */

function parts(iso: string, timeZone: string, options: Intl.DateTimeFormatOptions): Record<string, string> {
  const list = new Intl.DateTimeFormat("fr-FR", { ...options, timeZone }).formatToParts(new Date(iso));
  return Object.fromEntries(list.map((p) => [p.type, p.value]));
}

/** « 28/09 » dans le fuseau de l'instance. */
export function formatDayMonth(iso: string, timeZone: string): string {
  const p = parts(iso, timeZone, { day: "2-digit", month: "2-digit" });
  return `${p.day ?? ""}/${p.month ?? ""}`;
}

/** « 08/10/2026 » dans le fuseau de l'instance. */
export function formatDate(iso: string, timeZone: string): string {
  const p = parts(iso, timeZone, { day: "2-digit", month: "2-digit", year: "numeric" });
  return `${p.day ?? ""}/${p.month ?? ""}/${p.year ?? ""}`;
}

/** « 14:51 » dans le fuseau de l'instance. */
export function formatTime(iso: string, timeZone: string): string {
  const p = parts(iso, timeZone, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  return `${p.hour ?? ""}:${p.minute ?? ""}`;
}

/** Date sans heure (AAAA-MM-JJ) : lue en UTC pour ne jamais glisser d'un jour. */
export function formatDateOnly(date: string): string {
  return formatDate(`${date}T12:00:00Z`, "UTC");
}

/** « octobre 2026 » pour une période qui commence le 1er du mois. */
export function formatMonthYear(date: string): string {
  return new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
}

/** « d'octobre », « de septembre » : élision devant une voyelle (mois, périodes). */
export function withDe(word: string): string {
  return /^[aeiouyàâéèêîôû]/i.test(word) ? `d\u2019${word}` : `de ${word}`;
}

/** « octobre » seul. */
export function formatMonth(date: string): string {
  return new Intl.DateTimeFormat("fr-FR", { month: "long", timeZone: "UTC" }).format(new Date(`${date}T12:00:00Z`));
}

/** Nom du pays en français (« la France » n'est pas déduit : « France »). */
export function countryName(code: string): string {
  try {
    return new Intl.DisplayNames(["fr"], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}
