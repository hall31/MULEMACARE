import { hasMessage, t } from "@/i18n";
import { ApiProblem, NetworkTimeout, NetworkUnavailable } from "./client";

export { isAccessDenied } from "./client";

/**
 * Erreur prête à afficher (contrat de design §8) : ce qui s'est passé, quoi faire, et un code
 * stable. Codes de l'API (`PAY-03`, `NOT-01`…) tels quels ; codes propres au client pour le
 * réseau, qui n'atteint pas l'API : `E-NET-01` téléphone hors ligne, `E-NET-02` serveur
 * injoignable, `E-NET-03` délai dépassé. Réponse hors contrat : `SYS-01`.
 */
export interface UiError {
  text: string;
  detail: string;
  code: string;
}

export function toUiError(error: unknown): UiError {
  if (error instanceof NetworkUnavailable) {
    return error.offline
      ? { text: t("error.offline"), detail: t("error.offline.action"), code: "E-NET-01" }
      : { text: t("error.network"), detail: t("error.network.action"), code: "E-NET-02" };
  }
  if (error instanceof NetworkTimeout) return { text: t("error.timeout"), detail: t("error.timeout.action"), code: "E-NET-03" };
  if (error instanceof ApiProblem) {
    const { problem } = error;
    const key = `error.code.${problem.code}`;
    const fallback = hasMessage(key) ? t(key) : t("error.unexpected");
    return {
      text: problem.message || fallback,
      detail: problem.action || t("error.unexpected.action"),
      code: problem.code,
    };
  }
  return { text: t("error.unexpected"), detail: t("error.unexpected.action"), code: "SYS-01" };
}

export function problemCode(error: unknown): string | null {
  return error instanceof ApiProblem ? error.problem.code : null;
}

export function isOfflineError(error: unknown): boolean {
  return error instanceof NetworkUnavailable || error instanceof NetworkTimeout;
}
