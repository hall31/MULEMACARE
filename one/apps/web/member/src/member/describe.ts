import type { MyContribution } from "@/api/types";
import { t, type MessageKey } from "@/i18n";
import { countryName, formatDate, formatDateOnly, formatMonth, formatMonthYear, withDe } from "@/lib/format";

/** Libellés composés des cotisations (aucun nom de payeur : le contrat n'en garde pas, Q-P1-05). */
export function contributionTitle(c: MyContribution): string {
  return t("contribution.title", { month: withDe(formatMonth(c.period_start)) });
}

export function contributionPeriod(c: MyContribution): string {
  return formatMonthYear(c.period_start);
}

export function contributionLine(c: MyContribution, timeZone: string): string {
  if (c.status === "payee") {
    const parts = [c.paid_at ? t("contribution.paidOn", { date: formatDate(c.paid_at, timeZone) }) : t("contribution.status.payee")];
    if (c.payer_kind === "proche") {
      parts.push(c.payer_country_code ? t("contribution.payer.procheFrom", { country: countryName(c.payer_country_code) }) : t("contribution.payer.proche"));
    } else if (c.payer_kind) {
      parts.push(t(`contribution.payer.${c.payer_kind}` as MessageKey));
    }
    if (c.channel) parts.push(t("contribution.via", { channel: t(`channel.${c.channel}` as MessageKey) }));
    return parts.join(" · ");
  }
  if (c.status === "annulee") return t("contribution.cancelled");
  return t(c.status === "en_retard" ? "contribution.lateSince" : "contribution.dueOn", { date: formatDateOnly(c.due_on) });
}
