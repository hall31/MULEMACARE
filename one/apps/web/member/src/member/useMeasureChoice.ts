"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import {
  MEASURE_CHANGE_EVENT,
  MEASURE_CHOICE_KEY,
  browserChoiceStore,
  migrateLegacyChoice,
  readMeasureChoice,
  writeMeasureChoice,
  type MeasureChoice,
} from "@/lib/measure-consent";

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

/** Choix de mesure du téléphone ; `undefined` au rendu serveur (rien affiché, pas de saut). */
export function useMeasureChoice(): [MeasureChoice | null | undefined, (choice: MeasureChoice) => void] {
  useEffect(() => {
    const store = browserChoiceStore();
    if (store) migrateLegacyChoice(store);
  }, []);
  const choice = useSyncExternalStore<MeasureChoice | null | undefined>(subscribe, snapshot, () => undefined);
  const set = useCallback((next: MeasureChoice) => {
    const store = browserChoiceStore();
    if (store) writeMeasureChoice(store, next);
    window.dispatchEvent(new Event(MEASURE_CHANGE_EVENT));
  }, []);
  return [choice, set];
}
