"use client";

import { t } from "@/i18n";
import type { StepName } from "./ui";
import { Button, Icon } from "./ui";

/**
 * Bulle d'aide de première utilisation : sobre (ton info, pas d'animation), non bloquante (posée
 * au-dessus de l'écran, sans voile ni focus capturé), retirée par « Compris » pour cet écran, ou
 * désactivée pour tous les écrans. Réactivable par le bouton « Aide » de la barre du haut.
 */
export function CoachMark({ step, onGotIt, onDisable }: { step: StepName; onGotIt: () => void; onDisable: () => void }) {
  return (
    <aside className="flash" aria-labelledby="coach-t" data-testid="coach-mark" data-step={step}>
      <div className="alert tone-info coach">
        <Icon name="info" />
        <div className="alert-body">
          <b id="coach-t">{t("help.title")}</b>
          <span>{t(`help.${step}` as const)}</span>
          <div className="coach-actions">
            <Button variant="secondary" onClick={onGotIt}>
              {t("help.gotIt")}
            </Button>
            <Button variant="secondary" onClick={onDisable}>
              {t("help.disable")}
            </Button>
          </div>
        </div>
      </div>
    </aside>
  );
}
