import { t } from "@/i18n";

/**
 * Formats français (POLISH_CONTRACT §4) : espace fine insécable entre milliers, espace insécable
 * avant l'unité, virgule décimale. Montants entiers en francs CFA (AGENTS.md, Argent).
 */
const integer = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const decimal1 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function formatInteger(value: number): string {
  return integer.format(value);
}

export function formatMoney(amount: number): string {
  if (!Number.isInteger(amount)) throw new Error(`Montant non entier refusé : ${amount}`);
  return t("format.xof", { amount: integer.format(amount) });
}

/** Montant publié, arrondi au millier par l'API (CR-P3-02) : affiché comme approché. */
export function formatMoneyApprox(amount: number): string {
  return t("format.approx", { value: formatMoney(amount) });
}

/** Points de base → pourcentage à une décimale (6 842 → « 68,4 % »). */
export function formatBasisPoints(bp: number): string {
  return t("format.percent", { value: decimal1.format(bp / 100) });
}

/** Durée lisible (délai de décision) : secondes, minutes, heures ou jours. */
export function formatDuration(ms: number): string {
  const minutes = ms / 60_000;
  if (minutes < 1) return t("format.seconds", { value: integer.format(Math.round(ms / 1000)) });
  if (minutes < 60) return t("format.minutes", { value: integer.format(Math.round(minutes)) });
  const hours = minutes / 60;
  if (hours < 48) return t("format.hours", { value: decimal1.format(hours) });
  return t("format.days", { value: decimal1.format(hours / 24) });
}

/** Date calendaire `AAAA-MM-JJ` → `JJ/MM/AAAA`, sans conversion de fuseau. */
export function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

/** Horodatage UTC affiché dans le fuseau de l'organisation. */
export function formatDateTime(iso: string, timeZone = "Africa/Abidjan"): string {
  return new Intl.DateTimeFormat("fr-FR", { timeZone, dateStyle: "short", timeStyle: "short" }).format(new Date(iso));
}

/**
 * N semaines civiles ENTIÈRES et TERMINÉES (lundi → dimanche, fuseau de l'organisation), la
 * dernière finissant le dimanche passé : la période demandée est celle que l'API publie
 * (CR-P3-02), jamais la semaine en cours ni le futur.
 */
export function weeksPeriod(weeks: number, now: Date, timeZone = "Africa/Abidjan"): { from: string; to: string } {
  const today = periodOf(1, now, timeZone).to;
  const day = new Date(`${today}T00:00:00Z`);
  const mondayOffset = (day.getUTCDay() + 6) % 7;
  const lastSunday = new Date(day.getTime() - (mondayOffset + 1) * 86_400_000);
  const firstMonday = new Date(lastSunday.getTime() - (weeks * 7 - 1) * 86_400_000);
  return { from: firstMonday.toISOString().slice(0, 10), to: lastSunday.toISOString().slice(0, 10) };
}

/** Période de N jours se terminant aujourd'hui (jours locaux, bornes incluses). */
export function periodOf(days: number, now: Date, timeZone = "Africa/Abidjan"): { from: string; to: string } {
  const fmt = (d: Date) => new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  return { from: fmt(new Date(now.getTime() - (days - 1) * 86_400_000)), to: fmt(now) };
}
