import { describe, expect, it } from "vitest";
import fr from "@/i18n/fr.json";
import { STORAGE_PREFIX } from "@/lib/device-data";
import {
  COVERAGE_EXAMPLE_XOF,
  READING_WORDS_PER_MINUTE,
  STEP1_TEXT_KEYS,
  TOUR_KEY,
  TOUR_STEPS,
  checkChoices,
  coverageExample,
  readTour,
  resetTour,
  shouldInvite,
  wordCount,
  writeTour,
} from "./tour";

function memoryStore(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

describe("parcours de première visite : trois étapes, passable, rejouable", () => {
  it("trois étapes dans l'ordre : couverture, carte au comptoir, suivi d'un remboursement", () => {
    expect(TOUR_STEPS).toEqual(["couverture", "carte", "suivi"]);
  });

  it("première visite : invitation tant que rien n'est enregistré ; plus après terminé ou passé", () => {
    const store = memoryStore();
    expect(shouldInvite(readTour(store))).toBe(true);
    writeTour(store, "passe", new Date("2026-10-01T09:00:00Z"));
    expect(shouldInvite(readTour(store))).toBe(false);
    writeTour(store, "termine", new Date("2026-10-01T09:02:00Z"));
    expect(readTour(store)).toEqual({ state: "termine", at: "2026-10-01T09:02:00.000Z" });
    resetTour(store);
    expect(shouldInvite(readTour(store))).toBe(true);
  });

  it("mémorisé sous le préfixe de l'espace (effacé à la déconnexion), sans aucune donnée de l'adhérent", () => {
    expect(TOUR_KEY.startsWith(STORAGE_PREFIX)).toBe(true);
    const store = memoryStore();
    writeTour(store, "termine", new Date("2026-10-01T09:00:00Z"));
    const raw = store.data.get(TOUR_KEY) ?? "";
    expect(Object.keys(JSON.parse(raw) as object).sort()).toEqual(["at", "state", "v"]);
    expect(raw).not.toMatch(/MC-|FCFA|xof|person|card|name|Awa/i);
  });

  it("valeur illisible ou d'une autre version : considérée comme première visite, sans exception", () => {
    expect(shouldInvite(readTour(memoryStore({ [TOUR_KEY]: "{pas du json" })))).toBe(true);
    expect(shouldInvite(readTour(memoryStore({ [TOUR_KEY]: JSON.stringify({ v: 9, state: "termine" }) })))).toBe(true);
    const refused = { getItem: () => { throw new Error("refusé"); }, setItem: () => { throw new Error("refusé"); }, removeItem: () => { throw new Error("refusé"); } };
    expect(() => writeTour(refused, "passe", new Date())).not.toThrow();
    expect(readTour(refused)).toBeNull();
  });
});

describe("comprendre sa couverture : exemple chiffré tiré du taux de la carte", () => {
  it("80 % sur 10 000 FCFA : la mutuelle paie 8 000, l'adhérent 2 000 (entiers)", () => {
    expect(COVERAGE_EXAMPLE_XOF).toBe(10_000);
    expect(coverageExample(8000)).toEqual({ total: 10_000, covered: 8_000, patient: 2_000 });
  });

  it("taux non rond : part mutuelle à l'entier inférieur (Q-L2-03), la somme reste exacte", () => {
    const ex = coverageExample(7333);
    expect(ex.covered).toBe(7_333);
    expect(ex.covered + ex.patient).toBe(10_000);
    expect(Number.isInteger(ex.covered) && Number.isInteger(ex.patient)).toBe(true);
    expect(coverageExample(0)).toEqual({ total: 10_000, covered: 0, patient: 10_000 });
    expect(coverageExample(10_000)).toEqual({ total: 10_000, covered: 10_000, patient: 0 });
  });

  it("question de vérification : trois réponses distinctes, une seule juste (la part de l'adhérent)", () => {
    const choices = checkChoices(8000);
    expect(new Set(choices.map((c) => c.amount)).size).toBe(3);
    expect(choices.filter((c) => c.correct)).toEqual([{ amount: 2_000, correct: true }]);
    // Taux de 50 % : part mutuelle = part adhérent ; les choix restent distincts.
    expect(new Set(checkChoices(5000).map((c) => c.amount)).size).toBe(3);
    expect(checkChoices(5000).filter((c) => c.correct)).toHaveLength(1);
  });

  it("objectif « moins de 2 minutes » : l'étape 1 se lit en moins d'une minute et demie", () => {
    const words = STEP1_TEXT_KEYS.reduce((sum, key) => sum + wordCount(fr[key]), 0);
    // Lecture lente (lecteurs peu à l'aise à l'écrit) : 100 mots par minute. Le reste du temps
    // sert à répondre à la question de vérification.
    expect(READING_WORDS_PER_MINUTE).toBe(100);
    expect(words / READING_WORDS_PER_MINUTE).toBeLessThanOrEqual(1.5);
  });
});
