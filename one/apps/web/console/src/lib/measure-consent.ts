/**
 * Consentement à la mesure produit, sur ce navigateur. Les événements portent un identifiant de
 * session tiré au hasard : c'est un pseudonyme, pas un anonymat (droit ivoirien et sénégalais des
 * données personnelles). La mesure reste donc désactivée tant que la personne n'a pas choisi.
 *
 * Choix explicite (« granted » ou « refused »), réversible à tout moment, gardé sans aucune donnée
 * personnelle (`{ v, choice }`), hors de toute clé de session : il survit à la déconnexion et au
 * changement de profil.
 */
export type MeasureChoice = "granted" | "refused";

export const MEASURE_CHOICE_KEY = "mulemacare-one.console.mesure.choix";
/** Ancien interrupteur (« off ») : un refus déjà exprimé reste un refus. */
const LEGACY_OFF_KEY = "mulemacare-one.console.mesure";
const CHANGE_EVENT = "mulema:measure-choice";

function storage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function readMeasureChoice(): MeasureChoice | null {
  const store = storage();
  if (!store) return null;
  try {
    const raw = store.getItem(MEASURE_CHOICE_KEY);
    if (raw) {
      const value = JSON.parse(raw) as { v?: unknown; choice?: unknown };
      if (value.v === 1 && (value.choice === "granted" || value.choice === "refused")) return value.choice;
      return null;
    }
    return store.getItem(LEGACY_OFF_KEY) === "off" ? "refused" : null;
  } catch {
    return null;
  }
}

export function setMeasureChoice(choice: MeasureChoice): void {
  const store = storage();
  if (!store) return;
  try {
    store.setItem(MEASURE_CHOICE_KEY, JSON.stringify({ v: 1, choice }));
    store.removeItem(LEGACY_OFF_KEY);
  } catch {
    // Stockage refusé : aucun choix gardé, la mesure reste désactivée.
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/** La mesure est coupée pour toute l'instance (`NEXT_PUBLIC_MULEMA_TELEMETRY=off`). */
export function measureOffForInstance(): boolean {
  return process.env.NEXT_PUBLIC_MULEMA_TELEMETRY === "off";
}

/** Abonnement aux changements du choix (cet onglet et les autres). */
export function subscribeMeasureChoice(callback: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === MEASURE_CHOICE_KEY) callback();
  };
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback);
    window.removeEventListener("storage", onStorage);
  };
}
