"use client";

import type { TrackingStep } from "@/api/types";
import { t } from "@/i18n";
import { Icon } from "@/ui/ui";
import { trackingView, type StepLook } from "./tracking";

const DOT_ICON: Partial<Record<StepLook, "check" | "x" | "minus">> = { done: "check", refused: "x", cancelled: "minus" };

/**
 * Frise d'étapes (planche, « Mon remboursement ») : fait = ok coché, en cours = royal (info),
 * refus = crit. L'état est aussi dit en mots (texte masqué pour la pastille, détail visible).
 */
export function Timeline({ steps, timeZone, labelledBy }: { steps: readonly TrackingStep[]; timeZone: string; labelledBy?: string }) {
  const view = trackingView(steps, timeZone);
  return (
    <ol className="tl" aria-labelledby={labelledBy} data-testid="timeline">
      {view.map((step) => {
        const icon = DOT_ICON[step.look];
        return (
          <li key={step.key} className={`tl-${step.look}`} data-step={step.key} data-state={step.state} aria-current={step.look === "current" ? "step" : undefined}>
            <span className="tl-dot" aria-hidden="true">
              {icon ? <Icon name={icon} /> : null}
            </span>
            <div>
              <b>
                {step.title}
                <span className="sr-only">{t("tracking.srState", { state: step.stateLabel })}</span>
              </b>
              <span>{step.detail}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
