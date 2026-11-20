import { describe, expect, it } from "vitest";
import fr from "@/i18n/fr.json";
import { HELP_KEY, HELP_STEPS, disableHelp, enableHelp, markSeen, readHelp, shouldShowHelp, writeHelp } from "./help";
import { offlineCapabilities } from "./offline-capabilities";

function memoryStore(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

describe("aide de première utilisation (coach marks)", () => {
  it("une aide par écran du comptoir, chacune traduite (titre et texte)", () => {
    expect(HELP_STEPS).toEqual(["card", "identity", "code", "acts", "decision"]);
    const keys = new Set(Object.keys(fr));
    for (const step of HELP_STEPS) {
      expect(keys.has(`help.${step}`), step).toBe(true);
    }
  });

  it("première utilisation : affichée une fois par écran, « Compris » la retire pour cet écran seulement", () => {
    let state = readHelp(memoryStore());
    expect(HELP_STEPS.every((s) => shouldShowHelp(state, s))).toBe(true);
    state = markSeen(state, "card");
    expect(shouldShowHelp(state, "card")).toBe(false);
    expect(shouldShowHelp(state, "identity")).toBe(true);
  });

  it("désactivable d'un geste, réactivable depuis la barre du haut (toutes les aides reviennent)", () => {
    let state = markSeen(readHelp(memoryStore()), "card");
    state = disableHelp(state);
    expect(HELP_STEPS.some((s) => shouldShowHelp(state, s))).toBe(false);
    state = enableHelp(state);
    expect(HELP_STEPS.every((s) => shouldShowHelp(state, s))).toBe(true);
  });

  it("mémorisée sur l'appareil, sans donnée de patient ; valeur illisible : aide affichée", () => {
    const store = memoryStore();
    writeHelp(store, disableHelp(markSeen(readHelp(store), "acts")));
    expect(JSON.parse(store.data.get(HELP_KEY) ?? "{}")).toEqual({ v: 1, off: true, seen: ["acts"] });
    expect(readHelp(store)).toEqual({ off: true, seen: ["acts"] });
    expect(readHelp(memoryStore({ [HELP_KEY]: "{x" }))).toEqual({ off: false, seen: [] });
    expect(readHelp(memoryStore({ [HELP_KEY]: JSON.stringify({ v: 1, off: false, seen: ["inconnu", "code"] }) }))).toEqual({ off: false, seen: ["code"] });
  });
});

describe("hors ligne : ce qui reste possible, ce qui ne l'est pas", () => {
  it("avant l'identification : rien de neuf sans réseau, l'identification est impossible", () => {
    const caps = offlineCapabilities({ identified: false, canSign: true, thresholdXof: 50_000, validityMinutes: 120 });
    expect(caps.can.map((c) => c.key)).toEqual(["net.can.finish"]);
    expect(caps.cannot.map((c) => c.key)).toEqual(["net.cannot.identify"]);
  });

  it("identifié, politique à jour : accord provisoire sous le seuil, valable au plus 2 h ; au-delà, médecin-conseil", () => {
    const caps = offlineCapabilities({ identified: true, canSign: true, thresholdXof: 50_000, validityMinutes: 300 });
    expect(caps.can).toEqual([
      { key: "net.can.provisional", params: { threshold: 50_000, duration: "2 h" } },
      { key: "net.can.sync" },
    ]);
    expect(caps.cannot.map((c) => c.key)).toEqual(["net.cannot.above", "net.cannot.identify"]);
  });

  it("identifié sans politique valable : aucun accord provisoire, réessayer au retour du réseau", () => {
    const caps = offlineCapabilities({ identified: true, canSign: false, thresholdXof: null, validityMinutes: null });
    expect(caps.can.map((c) => c.key)).toEqual(["net.can.retry"]);
    expect(caps.cannot.map((c) => c.key)).toEqual(["net.cannot.provisional", "net.cannot.identify"]);
  });

  it("chaque ligne est traduite", () => {
    const keys = new Set(Object.keys(fr));
    for (const input of [
      { identified: false, canSign: false, thresholdXof: null, validityMinutes: null },
      { identified: true, canSign: true, thresholdXof: 50_000, validityMinutes: 60 },
      { identified: true, canSign: false, thresholdXof: null, validityMinutes: null },
    ]) {
      const caps = offlineCapabilities(input);
      for (const line of [...caps.can, ...caps.cannot]) expect(keys.has(line.key), line.key).toBe(true);
    }
  });
});
