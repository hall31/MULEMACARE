"use client";

import { useCallback, useId, useState, useSyncExternalStore } from "react";
import { t } from "@/i18n";
import { MEASURE_CHANGE_EVENT, MEASURE_CHOICE_KEY, browserChoiceStore, measureOffForInstance, readMeasureChoice, writeMeasureChoice, type MeasureChoice } from "@/lib/measure-consent";
import { Button, Icon } from "./ui";

function subscribe(callback: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === MEASURE_CHOICE_KEY) callback();
  };
  window.addEventListener(MEASURE_CHANGE_EVENT, callback);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(MEASURE_CHANGE_EVENT, callback);
    window.removeEventListener("storage", onStorage);
  };
}

function snapshot(): MeasureChoice | null {
  const store = browserChoiceStore();
  return store ? readMeasureChoice(store) : null;
}

/** Choix de mesure de l'appareil ; `undefined` au rendu serveur (rien affiché, pas de saut). */
export function useMeasureChoice(): [MeasureChoice | null | undefined, (choice: MeasureChoice) => void] {
  const choice = useSyncExternalStore<MeasureChoice | null | undefined>(subscribe, snapshot, () => undefined);
  const set = useCallback((next: MeasureChoice) => {
    const store = browserChoiceStore();
    if (store) writeMeasureChoice(store, next);
    window.dispatchEvent(new Event(MEASURE_CHANGE_EVENT));
  }, []);
  return [choice, set];
}

/**
 * Bulle de premier usage : sobre (ton info, sans voile ni focus capturé, le parcours avance sans
 * la fermer), tant que la clinique n'a pas choisi. Deux choix de même poids ; « En savoir plus »
 * déplie un court texte. Sans choix, la mesure est désactivée.
 */
export function MeasureConsent() {
  const [choice, setChoice] = useMeasureChoice();
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const detailsId = useId();
  if (choice !== null || measureOffForInstance()) return null;
  return (
    <section className="flash" aria-labelledby={titleId} data-testid="measure-consent">
      <div className="alert tone-info coach">
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
          <div className="coach-actions">
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

/**
 * Interrupteur de la mesure, sur l'écran Carte (début de chaque patient) : ligne pleine largeur de
 * 48 px, état dit en mots. Éteint tant qu'aucun choix ; allumer vaut accord, éteindre vaut refus.
 * Pas dans la barre du haut : à 360 px, un quatrième bouton y repousse tout l'écran.
 */
export function MeasureSwitchRow() {
  const [choice, setChoice] = useMeasureChoice();
  const hintId = useId();
  if (measureOffForInstance()) return null;
  // Rendu serveur (choix encore inconnu) : la ligne est peinte tout de suite, éteinte, ce qui est
  // l'état réel tant qu'aucun choix n'est fait ; rien n'apparaît tard (LCP, CLS).
  const on = choice === "granted";
  return (
    <div className="measure-row">
      <button type="button" role="switch" aria-checked={on} aria-describedby={hintId} onClick={() => setChoice(on ? "refused" : "granted")} className="measure-switch" data-testid="measure-switch">
        <Icon name="chart" />
        <span className="measure-switch-label">{t("measure.switch")}</span>
        <span aria-hidden="true">{t(on ? "measure.on" : "measure.off")}</span>
      </button>
      <p id={hintId}>{t("measure.switchHint")}</p>
    </div>
  );
}
