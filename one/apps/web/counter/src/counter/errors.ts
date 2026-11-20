import { ApiProblem, NetworkTimeout, NetworkUnavailable } from "@/api/client";
import { hasMessage, t, tp } from "@/i18n";

export interface UiMessage {
  text: string;
  detail?: string;
  /** Code stable de l'API (`ID-03`, `R-01`…), affiché avec le message (contrat de design §8). */
  code?: string;
}

/** Message affiché au comptoir : celui de l'API (déjà en français simple), sinon le fichier de traduction. */
export function toUiMessage(error: unknown): UiMessage {
  if (error instanceof NetworkUnavailable) return { text: t("error.network") };
  if (error instanceof NetworkTimeout) return { text: t("error.timeout") };
  if (error instanceof ApiProblem) {
    const { problem } = error;
    const key = `error.code.${problem.code}`;
    const text = problem.message || (hasMessage(key) ? t(key) : t("error.unexpected"));
    const details = [problem.action];
    if (problem.code === "ID-03" && typeof problem.remaining_attempts === "number" && !problem.message.includes(String(problem.remaining_attempts))) {
      details.push(tp("error.attempts", problem.remaining_attempts));
    }
    const detail = details.filter(Boolean).join(" ");
    return detail ? { text, detail, code: problem.code } : { text, code: problem.code };
  }
  return { text: t("error.unexpected") };
}
