import type { ClaimStatus, ContributionStatus, MyBeneficiary, MyCard } from "@/api/types";
import type { MessageKey } from "@/i18n";

/**
 * Statuts : couleurs sémantiques seulement (ok / warn / crit / info / neutre), jamais l'accent
 * (docs/POLISH_CONTRACT.md §5). Toujours une icône ET un mot.
 */
export type StatusTone = "ok" | "warn" | "crit" | "info" | "neutral";
export type StatusIcon = "check" | "alert" | "clock" | "info" | "x" | "lock" | "minus";

export interface StatusLook {
  tone: StatusTone;
  icon: StatusIcon;
  label: MessageKey;
}

export const TONE_CLASS: Record<StatusTone, string> = {
  ok: "tone-ok",
  warn: "tone-warn",
  crit: "tone-crit",
  info: "tone-info",
  neutral: "tone-neutral",
};

/** §5 : accordé, payé → ok ; en revue → warn ; refusé → crit ; en cours, pièces demandées → info ; annulé → neutre. */
export const CLAIM_STATUS: Record<ClaimStatus, StatusLook> = {
  demandee: { tone: "info", icon: "clock", label: "claim.status.demandee" },
  accordee_auto: { tone: "ok", icon: "check", label: "claim.status.accordee_auto" },
  en_revue: { tone: "warn", icon: "clock", label: "claim.status.en_revue" },
  pieces_demandees: { tone: "info", icon: "info", label: "claim.status.pieces_demandees" },
  accordee: { tone: "ok", icon: "check", label: "claim.status.accordee" },
  refusee: { tone: "crit", icon: "x", label: "claim.status.refusee" },
  payee: { tone: "ok", icon: "check", label: "claim.status.payee" },
  annulee: { tone: "neutral", icon: "minus", label: "claim.status.annulee" },
};

/** Échéance : payée → ok ; à payer (échéance proche) → warn ; en retard → crit ; annulée → neutre. */
export const CONTRIBUTION_STATUS: Record<ContributionStatus, StatusLook> = {
  a_payer: { tone: "warn", icon: "clock", label: "contribution.status.a_payer" },
  payee: { tone: "ok", icon: "check", label: "contribution.status.payee" },
  en_retard: { tone: "crit", icon: "alert", label: "contribution.status.en_retard" },
  annulee: { tone: "neutral", icon: "minus", label: "contribution.status.annulee" },
};

export const BENEFICIARY_CARD: Record<MyBeneficiary["card_status"], StatusLook> = {
  active: { tone: "ok", icon: "check", label: "beneficiary.card.active" },
  bloquee: { tone: "crit", icon: "lock", label: "beneficiary.card.bloquee" },
  aucune: { tone: "neutral", icon: "minus", label: "beneficiary.card.aucune" },
};

/** Droits de la carte : ouverts, carence, suspendus ; une carte bloquée passe avant tout. */
export function rightsLook(card: Pick<MyCard, "card_status" | "entitlements">): StatusLook {
  if (card.card_status === "bloquee") return { tone: "crit", icon: "lock", label: "rights.blocked" };
  if (card.entitlements.rights_open) return { tone: "ok", icon: "check", label: "rights.open" };
  if (card.entitlements.status === "carence") return { tone: "warn", icon: "clock", label: "rights.waiting" };
  if (card.entitlements.status === "suspendu") return { tone: "crit", icon: "alert", label: "rights.suspended" };
  return { tone: "crit", icon: "alert", label: "rights.closed" };
}
