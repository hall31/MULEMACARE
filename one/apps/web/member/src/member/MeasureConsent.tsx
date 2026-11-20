"use client";

import { useId, useState } from "react";
import { t } from "@/i18n";
import { measureOffForInstance } from "@/lib/measure-consent";
import { Button, Icon } from "@/ui/ui";
import { useMeasureChoice } from "./useMeasureChoice";

/**
 * Bandeau de premier usage : sobre (ton info, sans voile ni focus capturé), tant que l'adhérent
 * n'a pas choisi. Deux choix de même poids ; « En savoir plus » déplie un court texte. Sans
 * choix, la mesure est désactivée.
 */
export default function MeasureConsent() {
  const [choice, setChoice] = useMeasureChoice();
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const detailsId = useId();
  if (choice !== null || measureOffForInstance()) return null;
  return (
    <section className="m-consent" aria-labelledby={titleId} data-testid="measure-consent">
      <div className="alert tone-info">
        <Icon name="info" />
        <div className="alert-body">
          <b id={titleId}>{t("measure.title")}</b>
          <span>{t("measure.text")}</span>
          {open ? (
            <span id={detailsId} className="measure-details" data-testid="measure-details">
              <span>{t("measure.details.counted")}</span>
              <span>{t("measure.details.never")}</span>
              <span>{t("measure.details.pseudonymous")}</span>
              <span>{t("measure.details.change")}</span>
            </span>
          ) : null}
          <button type="button" className="linkbtn" aria-expanded={open} aria-controls={open ? detailsId : undefined} onClick={() => setOpen((v) => !v)}>
            {t("measure.learnMore")}
          </button>
          <div className="consent-actions">
            <Button variant="secondary" onClick={() => setChoice("granted")}>
              {t("measure.accept")}
            </Button>
            <Button variant="secondary" onClick={() => setChoice("refused")}>
              {t("measure.refuse")}
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
