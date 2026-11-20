/**
 * Consentement à la mesure produit sur ce téléphone. Les événements portent un identifiant de
 * session tiré au hasard : c'est un pseudonyme, pas un anonymat (droit ivoirien et sénégalais des
 * données personnelles). La mesure reste désactivée tant que l'adhérent n'a pas choisi.
 *
 * Choix explicite (« granted » ou « refused »), réversible depuis « Mes notifications ›
 * Préférences », gardé sans aucune donnée de l'adhérent (`{ v, choice }`) et HORS du préfixe
 * `mulema.adherent.` : il survit à la déconnexion (un refus n'est jamais oublié).
 */
export type MeasureChoice = "granted" | "refused";

export interface ChoiceStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export const MEASURE_CHOICE_KEY = "mulema.mesure.adherent";
/** Ancien interrupteur (« off », sous le préfixe, effacé à la déconnexion) : un refus reste un refus. */
const LEGACY_OFF_KEY = "mulema.adherent.mesure";
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
/** Reprend un ancien refus dans la clé qui survit à la déconnexion (avant qu'elle ne l'efface). */
export function migrateLegacyChoice(store: ChoiceStore): void {
  try {
    if (store.getItem(MEASURE_CHOICE_KEY) === null && store.getItem(LEGACY_OFF_KEY) === "off") writeMeasureChoice(store, "refused");
  } catch {
    // Stockage refusé : rien à reprendre.
  }
}

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
