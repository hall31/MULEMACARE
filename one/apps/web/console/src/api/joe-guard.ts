import { ApiError } from "./client";
import type { DecisionDraft, JoeAnswer } from "./types";
import { t } from "@/i18n";

/**
 * Le contrat interdit une réponse de JOE sans source (`JoeAnswer.sources` non vide si `kind` vaut
 * `reponse` ; `DecisionDraft.sources` : minItems 1). Une telle réponse n'est jamais affichée :
 * l'écran la traite comme une erreur, avec un code stable et « Réessayer ».
 */
export class UnsourcedAnswerError extends ApiError {
  readonly clientCode = "E-JOE-01";

  constructor() {
    super(502, { code: "SYS-01", message: t("joe.unsourced.message"), action: t("joe.unsourced.action"), request_id: "" });
    this.name = "UnsourcedAnswerError";
  }
}

export function requireSourcedAnswer(answer: JoeAnswer): JoeAnswer {
  if (answer.kind === "reponse" && (!Array.isArray(answer.sources) || answer.sources.length === 0)) throw new UnsourcedAnswerError();
  return answer;
}

export function requireSourcedDraft(draft: DecisionDraft): DecisionDraft {
  if (!Array.isArray(draft.sources) || draft.sources.length === 0) throw new UnsourcedAnswerError();
  return draft;
}
