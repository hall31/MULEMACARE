import type { MyContribution, PaymentLink } from "@/api/types";
import { t } from "@/i18n";
import { formatDate, formatMonthYear, formatXof, withDe } from "@/lib/format";

/**
 * Partage du lien de paiement créé par `createMyPaymentLink`. Ordre : partage natif du téléphone
 * (Web Share), sinon copie du lien. WhatsApp est proposé à côté, par un simple lien wa.me que
 * l'adhérent ouvre lui-même : l'application n'appelle aucun service tiers.
 */
export function inviteMessage(contribution: MyContribution, link: PaymentLink, timeZone: string): string {
  return t("invite.message", {
    period: withDe(formatMonthYear(contribution.period_start)),
    amount: formatXof(contribution.amount_xof),
    until: formatDate(link.expires_at, timeZone),
    url: link.url,
  });
}

export function whatsappUrl(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}

export interface ShareCapabilities {
  share?: (data: ShareData) => Promise<void>;
  clipboard?: { writeText(text: string): Promise<void> };
}

export type ShareOutcome = "shared" | "cancelled" | "copied" | "unavailable";

export async function shareInvite(caps: ShareCapabilities, data: { title: string; text: string; url: string }): Promise<ShareOutcome> {
  if (caps.share) {
    try {
      await caps.share(data);
      return "shared";
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return "cancelled";
      // Partage refusé par le navigateur : on retombe sur la copie.
    }
  }
  return copyLink(caps, data.url);
}

export async function copyLink(caps: ShareCapabilities, url: string): Promise<ShareOutcome> {
  if (!caps.clipboard) return "unavailable";
  try {
    await caps.clipboard.writeText(url);
    return "copied";
  } catch {
    return "unavailable";
  }
}

/** Capacités du navigateur courant (le partage natif n'existe pas partout, ni sur ordinateur). */
export function browserShareCapabilities(): ShareCapabilities {
  if (typeof navigator === "undefined") return {};
  const caps: ShareCapabilities = {};
  if (typeof navigator.share === "function") caps.share = (data) => navigator.share(data);
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") caps.clipboard = navigator.clipboard;
  return caps;
}
