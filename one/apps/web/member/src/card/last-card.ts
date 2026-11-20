import type { MyCard } from "@/api/types";

/**
 * Dernière carte lisible hors ligne. On garde l'identité de la carte et les droits À LA DATE DE
 * LECTURE, jamais le QR : un QR périmé serait refusé au comptoir (et une capture d'écran ne
 * doit pas fonctionner). Stockage local du téléphone de l'adhérent, une seule carte, aucune
 * donnée médicale (le contrat n'en renvoie pas).
 */
export const LAST_CARD_KEY = "mulema.adherent.derniere-carte";

/**
 * Âge maximal de la carte enregistrée (QUESTIONS.md Q-P1W-11, défaut 24 h) : au-delà, les droits
 * ont pu changer (carence, suspension, révocation) ; la carte n'est plus affichée et elle est
 * effacée. Une date d'enregistrement dans le futur (horloge reculée) compte comme trop ancienne.
 */
export const MAX_SAVED_CARD_AGE_MS = 24 * 60 * 60_000;

/** Tolérance d'horloge pour une date d'enregistrement légèrement dans le futur. */
const CLOCK_SKEW_MS = 5 * 60_000;

export type StoredCard = Omit<MyCard, "qr_payload" | "qr_generated_at" | "qr_refresh_at">;

export interface CardSnapshot {
  savedAt: string;
  card: StoredCard;
}

export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface Stored extends CardSnapshot {
  v: 1;
  /** `self` : carte demandée sans `person_id` (titulaire) ; sinon l'identifiant demandé. */
  personKey: string;
}

const keyOf = (personId: string | null) => personId ?? "self";

export function saveLastCard(store: KeyValueStore, card: MyCard, requestedPersonId: string | null, now: Date): void {
  // Destructuration explicite : le QR et ses dates ne sont jamais écrits.
  const { qr_payload: _payload, qr_generated_at: _generated, qr_refresh_at: _refresh, ...rest } = card;
  const stored: Stored = { v: 1, personKey: keyOf(requestedPersonId), savedAt: now.toISOString(), card: rest };
  try {
    store.setItem(LAST_CARD_KEY, JSON.stringify(stored));
  } catch {
    // Stockage plein ou refusé (navigation privée) : la carte hors ligne n'est simplement pas disponible.
  }
}

function isStoredCard(value: unknown): value is StoredCard {
  if (!value || typeof value !== "object") return false;
  const c = value as Record<string, unknown>;
  const ent = c.entitlements as Record<string, unknown> | undefined;
  return (
    typeof c.person_id === "string" &&
    typeof c.given_name === "string" &&
    typeof c.family_name === "string" &&
    typeof c.member_number === "string" &&
    typeof c.plan_code === "string" &&
    typeof c.coverage_rate_bp === "number" &&
    typeof c.card_status === "string" &&
    !!ent &&
    typeof ent.rights_open === "boolean" &&
    typeof ent.remaining_xof === "number" &&
    typeof ent.family_annual_ceiling_xof === "number" &&
    typeof ent.consumed_xof === "number"
  );
}

/** Lecture de la carte enregistrée : absente, affichable, ou trop ancienne (déjà effacée). */
export type LastCardRead = { kind: "none" } | { kind: "fresh"; snapshot: CardSnapshot } | { kind: "stale"; savedAt: string };

const NONE: LastCardRead = { kind: "none" };

/** Vrai si une carte enregistrée à `savedAt` ne doit plus être affichée à `now`. */
export function isTooOld(savedAt: string, now: number, maxAgeMs = MAX_SAVED_CARD_AGE_MS): boolean {
  const age = now - Date.parse(savedAt);
  return Number.isNaN(age) || age > maxAgeMs || age < -CLOCK_SKEW_MS;
}

export function readLastCard(store: KeyValueStore, requestedPersonId: string | null, now: number, maxAgeMs = MAX_SAVED_CARD_AGE_MS): LastCardRead {
  let value: Partial<Stored>;
  try {
    const raw = store.getItem(LAST_CARD_KEY);
    if (!raw) return NONE;
    value = JSON.parse(raw) as Partial<Stored>;
  } catch {
    return NONE;
  }
  if (value.v !== 1 || typeof value.savedAt !== "string" || Number.isNaN(Date.parse(value.savedAt))) return NONE;
  // Trop ancienne : effacée quelle que soit la personne ; seule la date est rendue.
  if (isTooOld(value.savedAt, now, maxAgeMs)) {
    clearLastCard(store);
    return value.personKey === keyOf(requestedPersonId) ? { kind: "stale", savedAt: value.savedAt } : NONE;
  }
  if (value.personKey !== keyOf(requestedPersonId) || !isStoredCard(value.card)) return NONE;
  return { kind: "fresh", snapshot: { savedAt: value.savedAt, card: value.card } };
}

/** Efface la carte enregistrée (refus d'accès, déconnexion, carte trop ancienne). */
export function clearLastCard(store: KeyValueStore): void {
  try {
    store.removeItem(LAST_CARD_KEY);
  } catch {
    // Stockage refusé : rien n'a pu y être écrit non plus.
  }
}

/** localStorage du navigateur, ou rien (rendu serveur, stockage interdit). */
export function browserStore(): KeyValueStore | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}
