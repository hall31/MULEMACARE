/**
 * Consentement à la mesure produit sur cet appareil de comptoir. Les événements portent un
 * identifiant de session tiré au hasard : c'est un pseudonyme, pas un anonymat (droit ivoirien et
 * sénégalais des données personnelles). La mesure reste désactivée tant que personne n'a choisi.
 *
 * Choix explicite (« granted » ou « refused »), réversible depuis la barre du haut, gardé sans
 * aucune donnée de patient (`{ v, choice }`) ; jamais effacé par « Patient suivant ».
 */
export type MeasureChoice = "granted" | "refused";

export interface ChoiceStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export const MEASURE_CHOICE_KEY = "mulema.comptoir.mesure.choix";
/** Ancien interrupteur (« off ») : un refus déjà exprimé reste un refus. */
const LEGACY_OFF_KEY = "mulema.comptoir.mesure";
export const MEASURE_CHANGE_EVENT = "mulema:measure-choice";

export function readMeasureChoice(store: ChoiceStore): MeasureChoice | null {
  try {
    const raw = store.getItem(MEASURE_CHOICE_KEY);
    if (raw) {
      const value = JSON.parse(raw) as { v?: unknown; choice?: unknown };
      return value.v === 1 && (value.choice === "granted" || value.choice === "refused") ? value.choice : null;
    }
    return store.getItem(LEGACY_OFF_KEY) === "off" ? "refused" : null;
  } catch {
    return null;
  }
}

export function writeMeasureChoice(store: ChoiceStore, choice: MeasureChoice): void {
  try {
    store.setItem(MEASURE_CHOICE_KEY, JSON.stringify({ v: 1, choice }));
    store.removeItem(LEGACY_OFF_KEY);
  } catch {
    // Stockage refusé : aucun choix gardé, la mesure reste désactivée.
  }
}

/** Seul un accord explicite active la mesure ; l'instance peut la couper pour tous. */
export function measureAllowed(choice: MeasureChoice | null, offForInstance: boolean): boolean {
  return !offForInstance && choice === "granted";
}

export function measureOffForInstance(): boolean {
  return process.env.NEXT_PUBLIC_MULEMA_TELEMETRY === "off";
}

/** Stockage du navigateur, ou rien (rendu serveur, stockage interdit). */
export function browserChoiceStore(): ChoiceStore | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}
