import type { KeyValueStore } from "@/card/last-card";
import type { MessageKey } from "@/i18n";

/**
 * Parcours de première visite de l'espace adhérent (Phase 2, voie A) : trois étapes, passable et
 * rejouable, sans formation. Objectif mesurable : comprendre sa couverture en moins de 2 minutes
 * (texte de l'étape 1 lisible en moins d'une minute et demie, plus une question de vérification ;
 * mesure réelle avec des adhérents : docs/USABILITY_PROTOCOL.md, tâche T1).
 *
 * Mémorisé sur le téléphone sous le préfixe de l'espace (effacé à la déconnexion) : seulement
 * l'état du parcours et sa date, jamais une donnée de l'adhérent.
 */
export const TOUR_KEY = "mulema.adherent.decouverte";

export const TOUR_STEPS = ["couverture", "carte", "suivi"] as const;
export type TourStep = (typeof TOUR_STEPS)[number];

export type TourState = "termine" | "passe";
export interface TourRecord {
  state: TourState;
  at: string;
}

interface Stored extends TourRecord {
  v: 1;
}

export function readTour(store: KeyValueStore): TourRecord | null {
  try {
    const raw = store.getItem(TOUR_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<Stored>;
    if (value.v !== 1 || (value.state !== "termine" && value.state !== "passe") || typeof value.at !== "string") return null;
    return { state: value.state, at: value.at };
  } catch {
    return null;
  }
}

export function writeTour(store: KeyValueStore, state: TourState, now: Date): void {
  const stored: Stored = { v: 1, state, at: now.toISOString() };
  try {
    store.setItem(TOUR_KEY, JSON.stringify(stored));
  } catch {
    // Stockage refusé (navigation privée) : l'invitation reviendra, sans autre conséquence.
  }
}

/** Rejouer : l'invitation de première visite réapparaît. */
export function resetTour(store: KeyValueStore): void {
  try {
    store.removeItem(TOUR_KEY);
  } catch {
    // Stockage refusé : rien n'avait pu y être écrit.
  }
}

/** L'invitation n'apparaît qu'à la première visite (rien d'enregistré). */
export function shouldInvite(record: TourRecord | null): boolean {
  return record === null;
}

/* ------------------------------------------------------------------ exemple chiffré */

/** Montant de l'exemple : rond, pour que le calcul se fasse de tête. */
export const COVERAGE_EXAMPLE_XOF = 10_000;

export interface CoverageExample {
  total: number;
  covered: number;
  patient: number;
}

/**
 * Exemple tiré du taux de la carte (`coverage_rate_bp`), en entiers FCFA. Part mutuelle à l'entier
 * inférieur, comme le moteur de règles (specs/QUESTIONS.md Q-L2-03) ; la part de l'adhérent est le
 * reste. Un exemple, pas une décision : le comptoir affiche toujours le montant du moteur.
 */
export function coverageExample(rateBp: number, total = COVERAGE_EXAMPLE_XOF): CoverageExample {
  const bp = Math.min(10_000, Math.max(0, Math.trunc(rateBp)));
  const covered = Math.floor((total * bp) / 10_000);
  return { total, covered, patient: total - covered };
}

export interface CheckChoice {
  amount: number;
  correct: boolean;
}

/**
 * Question de vérification « combien payez-vous ? » : la part de l'adhérent (juste), la part de la
 * mutuelle et le total (deux confusions fréquentes). Si deux montants coïncident (taux de 50 %, 0 %
 * ou 100 %), un troisième distracteur à mi-chemin les départage. Ordre stable : croissant.
 */
export function checkChoices(rateBp: number): CheckChoice[] {
  const { total, covered, patient } = coverageExample(rateBp);
  const amounts = new Set<number>([patient, covered, total]);
  for (const extra of [Math.floor(total / 4), Math.floor((total * 3) / 4), Math.floor(total / 10)]) {
    if (amounts.size >= 3) break;
    amounts.add(extra);
  }
  return [...amounts]
    .slice(0, 3)
    .sort((a, b) => a - b)
    .map((amount) => ({ amount, correct: amount === patient }));
}

/* ------------------------------------------------------------------ budget de lecture */

/** Lecture lente retenue pour le budget (adhérents peu à l'aise à l'écrit). */
export const READING_WORDS_PER_MINUTE = 100;

/** Textes visibles de l'étape 1 (hors titre et boutons) : leur longueur est bornée par un test. */
export const STEP1_TEXT_KEYS = [
  "tour.couverture.lead",
  "tour.couverture.rate",
  "tour.couverture.where",
  "tour.couverture.example",
  "tour.couverture.ceiling",
  "tour.couverture.family.other",
  "tour.check.question",
  "tour.check.right",
] as const satisfies readonly MessageKey[];

export function wordCount(text: string): number {
  return text.split(/[\s  ]+/).filter((w) => /[\p{L}\p{N}{]/u.test(w)).length;
}
