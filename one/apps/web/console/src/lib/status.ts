import type { ClaimStatus, Contribution, MemberStatus, PlanVersionState } from "@/api/types";

/**
 * Tons des statuts. Uniquement la sémantique ok / warn / crit (ou neutre) :
 * jamais la couleur d'accent de marque (AGENTS.md, Design).
 */
export type Tone = "ok" | "warn" | "crit" | "info" | "neutral";

export const TONE_CLASSES: Record<Tone, string> = {
  ok: "bg-ok-bg text-ok",
  warn: "bg-warn-bg text-warn",
  crit: "bg-crit-bg text-crit",
  info: "bg-info-bg text-info",
  neutral: "bg-sunk text-fg-2",
};

export const CLAIM_STATUS_TONE: Record<ClaimStatus, Tone> = {
  demandee: "neutral",
  accordee_auto: "ok",
  en_revue: "warn",
  pieces_demandees: "warn",
  accordee: "ok",
  refusee: "crit",
  payee: "neutral",
  annulee: "neutral",
};

export const MEMBER_STATUS_TONE: Record<MemberStatus, Tone> = {
  actif: "ok",
  carence: "warn",
  suspendu: "crit",
};

export const CONTRIBUTION_STATUS_TONE: Record<Contribution["status"], Tone> = {
  a_payer: "warn",
  payee: "ok",
  en_retard: "crit",
  annulee: "neutral",
};

export const PLAN_VERSION_TONE: Record<PlanVersionState, Tone> = {
  brouillon: "neutral",
  soumise: "warn",
  en_vigueur: "ok",
  cloturee: "neutral",
};

/** Seuils d'affichage de la barre de risque (couleur seulement ; aucune décision n'en dépend). */
export function riskTone(score: number | null | undefined): Tone {
  if (score === null || score === undefined) return "neutral";
  if (score > 0.6) return "crit";
  if (score >= 0.2) return "warn";
  return "ok";
}

export function usageTone(ratio: number): Tone {
  if (ratio > 0.85) return "crit";
  if (ratio > 0.6) return "warn";
  return "ok";
}
