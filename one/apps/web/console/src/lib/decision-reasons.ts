import type { ClaimDecisionKind } from "@/api/types";

/**
 * Motifs administratifs codés des décisions humaines (DecideClaimRequest.reason_code).
 * PROVISOIRE : la liste officielle n'est pas encore définie (specs/QUESTIONS.md, Q-L0-13).
 * Ces codes respectent le format du contrat (^[A-Z]{1,4}-[0-9]{2}$) et sont à valider
 * avec le médecin-conseil avant la mise en production. Aucun texte libre : aucune donnée
 * médicale ne peut entrer dans la base assurance par ce formulaire.
 */
export const DECISION_REASONS: Record<ClaimDecisionKind, readonly string[]> = {
  accorder: ["ACC-01"],
  refuser: ["REF-01", "REF-02"],
  demander_pieces: ["PCS-01"],
} as const;

export const DECISION_REASON_PATTERN = /^[A-Z]{1,4}-[0-9]{2}$/;
