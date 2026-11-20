import { t } from "@/i18n";

/** Fuseau par défaut de l'instance ; remplacé par celui de l'organisation dès qu'il est connu. */
export const DEFAULT_TIMEZONE = "Africa/Abidjan";

const integer = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const decimal2 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const decimal1 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

/** Montant en francs CFA. L'API ne transporte que des entiers (AGENTS.md, Argent). */
export function formatMoney(amount: number, options: { unit?: boolean } = {}): string {
  if (!Number.isInteger(amount)) {
    throw new Error(`Montant non entier refusé : ${amount}`);
  }
  const value = integer.format(amount);
  return options.unit === false ? value : `${value} ${t("common.currency")}`;
}

export function formatScore(score: number): string {
  return decimal2.format(score);
}

/** Points de base → pourcentage (8000 → « 80 »). */
export function formatBasisPoints(bp: number): string {
  return decimal1.format(bp / 100);
}

/** Date calendaire (sans heure) : affichée telle quelle, sans conversion de fuseau. */
export function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

/** Horodatage UTC affiché dans le fuseau de l'organisation (AGENTS.md, Dates). */
export function formatDateTime(iso: string, timeZone: string = DEFAULT_TIMEZONE): string {
  const parts = new Intl.DateTimeFormat("fr-FR", {
    timeZone,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("day")}/${get("month")}/${get("year")} ${get("hour")}:${get("minute")}`;
}

export function formatLongDate(date: Date, timeZone: string = DEFAULT_TIMEZONE): string {
  const text = new Intl.DateTimeFormat("fr-FR", {
    timeZone,
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}
