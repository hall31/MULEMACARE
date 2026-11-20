import type { TrackingStep } from "@/api/types";
import { hasMessage, t, type MessageKey } from "@/i18n";
import { formatDayMonth, formatTime } from "@/lib/format";

/**
 * Frise du remboursement (getMyClaimTracking). `key` et `state` sont des codes du contrat ; les
 * libellés viennent du fichier de traduction. Une étape que le contrat ne date pas (virement,
 * réception : Q-P1-03) reste dite par son état (« En cours »), jamais par une date inventée.
 */
export type StepLook = "done" | "current" | "todo" | "refused" | "cancelled" | "na";

export interface StepView {
  key: TrackingStep["key"];
  state: TrackingStep["state"];
  look: StepLook;
  title: string;
  /** L'état en mots, pour les lecteurs d'écran et le plein soleil (jamais la couleur seule). */
  stateLabel: string;
  detail: string;
}

const LOOK: Record<TrackingStep["state"], StepLook> = {
  fait: "done",
  en_cours: "current",
  a_venir: "todo",
  refuse: "refused",
  annule: "cancelled",
  sans_objet: "na",
};

/** Titre propre à un état (« Refusée par la mutuelle ») s'il existe, sinon le titre de l'étape. */
function title(step: TrackingStep): string {
  const specific = `tracking.step.${step.key}.${step.state}`;
  return hasMessage(specific) ? t(specific) : t(`tracking.step.${step.key}` as MessageKey);
}

function ruleText(step: TrackingStep): string | null {
  if (step.rule) return t("tracking.rule", { code: step.rule.code, version: step.rule.version });
  if (step.reason_code) return t("tracking.reason", { code: step.reason_code });
  return null;
}

export function trackingView(steps: readonly TrackingStep[], timeZone: string): StepView[] {
  return steps.map((step) => {
    const stateLabel = t(`tracking.state.${step.state}` as MessageKey);
    const when = step.at ? t("tracking.when", { day: formatDayMonth(step.at, timeZone), time: formatTime(step.at, timeZone) }) : null;
    const rule = ruleText(step);
    const detail = [when ?? stateLabel, rule].filter(Boolean).join(" · ");
    return { key: step.key, state: step.state, look: LOOK[step.state], title: title(step), stateLabel, detail };
  });
}
