"use client";

import { InfoIcon } from "lucide-react";
import { useCallback, useId, useState, useSyncExternalStore } from "react";
import { t } from "@/i18n";
import { cn } from "@/lib/cn";
import { measureOffForInstance, readMeasureChoice, setMeasureChoice, subscribeMeasureChoice, type MeasureChoice } from "@/lib/measure-consent";
import { Button } from "./ui/button";

/** Choix de mesure sur ce navigateur ; `undefined` au rendu serveur (rien n'est affiché). */
export function useMeasureChoice(): [MeasureChoice | null | undefined, (choice: MeasureChoice) => void] {
  const choice = useSyncExternalStore<MeasureChoice | null | undefined>(subscribeMeasureChoice, readMeasureChoice, () => undefined);
  const set = useCallback((next: MeasureChoice) => setMeasureChoice(next), []);
  return [choice, set];
}

function Details({ id }: { id: string }) {
  return (
    <div id={id} data-testid="measure-details" className="flex flex-col gap-1 pl-6 text-dense text-fg">
      <p>{t("measure.details.counted")}</p>
      <p>{t("measure.details.never")}</p>
      <p>{t("measure.details.pseudonymous")}</p>
      <p>{t("measure.details.change")}</p>
    </div>
  );
}

/**
 * Bandeau de premier usage : sobre (ton neutre, sans voile ni focus capturé), tant que la personne
 * n'a pas choisi. Deux choix de même poids, « En savoir plus » déplie un court texte. Tant qu'aucun
 * choix n'est fait, la mesure est désactivée.
 */
export function MeasureConsentBanner({ className }: { className?: string }) {
  const [choice, setChoice] = useMeasureChoice();
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const detailsId = useId();
  if (choice !== null || measureOffForInstance()) return null;
  return (
    <section role="region" aria-labelledby={titleId} data-testid="measure-banner" className={cn("flex flex-col gap-2 rounded-lg border border-line bg-surface p-4 text-dense", className)}>
      <div className="flex items-start gap-2">
        <InfoIcon className="mt-0.5 size-4 shrink-0 text-fg-2" aria-hidden />
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id={titleId} className="text-body font-semibold">
            {t("measure.banner.title")}
          </h2>
          <p>{t("measure.banner.text")}</p>
        </div>
      </div>
      {open ? <Details id={detailsId} /> : null}
      <div className="flex flex-wrap items-center gap-2 pl-6">
        <Button variant="outline" size="sm" onClick={() => setChoice("granted")}>
          {t("measure.accept")}
        </Button>
        <Button variant="outline" size="sm" onClick={() => setChoice("refused")}>
          {t("measure.refuse")}
        </Button>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={open ? detailsId : undefined}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex min-h-8 items-center px-1 text-dense text-brand underline underline-offset-2"
        >
          {t("measure.learnMore")}
        </button>
      </div>
    </section>
  );
}

/**
 * Interrupteur de la mesure, pour tous les rôles (menu de la console). Désactivé tant qu'aucun
 * choix n'est fait ; activer vaut acceptation, désactiver vaut refus.
 */
export function MeasureSwitch() {
  const [choice, setChoice] = useMeasureChoice();
  const hintId = useId();
  if (choice === undefined) return null;
  if (measureOffForInstance()) {
    return (
      <p className="text-caption text-fg-2" data-testid="measure-instance-off">
        {t("measure.switch")} · {t("measure.instanceOff")}
      </p>
    );
  }
  const on = choice === "granted";
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-describedby={hintId}
        data-testid="measure-switch"
        onClick={() => setChoice(on ? "refused" : "granted")}
        className="inline-flex min-h-8 w-full items-center gap-2 rounded-md border border-line-2 bg-surface px-2.5 text-dense font-medium hover:bg-sunk"
      >
        <span aria-hidden className={on ? "size-2 shrink-0 rounded-full bg-ok" : "size-2 shrink-0 rounded-full border border-line-2"} />
        <span className="flex-1 text-left whitespace-nowrap">{t("measure.switch")}</span>
        <span aria-hidden className="text-caption text-fg-2">
          {t(on ? "measure.on" : "measure.off")}
        </span>
      </button>
      <p id={hintId} className="text-caption text-fg-2">
        {t("measure.switchHint")}
      </p>
    </div>
  );
}
