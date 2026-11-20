import { describe, expect, it, vi } from "vitest";
import fr from "../i18n/fr.json";
import { HELP_KEY } from "../counter/help";
import { MEASURE_CHOICE_KEY, measureAllowed, readMeasureChoice, writeMeasureChoice } from "./measure-consent";
import { TELEMETRY_KEY, Telemetry, type ProductEventRequest } from "./telemetry";

function memoryStore(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

describe("consentement à la mesure (pseudonyme : désactivée tant que la clinique n'a pas choisi)", () => {
  it("aucun choix : pas de mesure", () => {
    const store = memoryStore();
    expect(readMeasureChoice(store)).toBeNull();
    expect(measureAllowed(readMeasureChoice(store), false)).toBe(false);
  });

  it("accepté puis refusé : réversible ; seul un accord explicite active la mesure", () => {
    const store = memoryStore();
    writeMeasureChoice(store, "granted");
    expect(measureAllowed(readMeasureChoice(store), false)).toBe(true);
    writeMeasureChoice(store, "refused");
    expect(readMeasureChoice(store)).toBe("refused");
    expect(measureAllowed(readMeasureChoice(store), false)).toBe(false);
  });

  it("instance coupée : jamais de mesure, même acceptée", () => {
    expect(measureAllowed("granted", true)).toBe(false);
  });

  it("valeur illisible ou inconnue : pas de choix ; ancien « off » : refus", () => {
    expect(readMeasureChoice(memoryStore({ [MEASURE_CHOICE_KEY]: "{x" }))).toBeNull();
    expect(readMeasureChoice(memoryStore({ [MEASURE_CHOICE_KEY]: JSON.stringify({ v: 1, choice: "oui" }) }))).toBeNull();
    expect(readMeasureChoice(memoryStore({ [TELEMETRY_KEY]: "off" }))).toBe("refused");
  });

  it("gardé sur l'appareil : le choix et sa version, aucune donnée de patient ; clé distincte de l'aide", () => {
    const store = memoryStore();
    writeMeasureChoice(store, "refused");
    expect(JSON.parse(store.data.get(MEASURE_CHOICE_KEY) ?? "null")).toEqual({ v: 1, choice: "refused" });
    expect(MEASURE_CHOICE_KEY).not.toBe(HELP_KEY);
  });
});

describe("envoi selon le choix", () => {
  const options = { surface: "comptoir" as const, role: "clinique" as const, getToken: () => "jeton" };

  it("désactivée : l'envoi n'est jamais appelé", async () => {
    const send = vi.fn(async () => undefined);
    const t = new Telemetry({ ...options, isOnline: () => true, isEnabled: () => false, send });
    t.track("offline_banner_seen");
    t.flush();
    await Promise.resolve();
    expect(send).not.toHaveBeenCalled();
  });

  it("refus pendant la coupure : ce qui attendait est oublié", async () => {
    let enabled = true;
    let online = false;
    const sent: ProductEventRequest[] = [];
    const t = new Telemetry({ ...options, isOnline: () => online, isEnabled: () => enabled, send: async (e) => void sent.push(e) });
    t.track("offline_banner_seen");
    enabled = false;
    online = true;
    t.flush();
    enabled = true;
    t.flush();
    await Promise.resolve();
    expect(sent).toEqual([]);
  });
});

describe("libellés honnêtes", () => {
  it("« mesure pseudonyme, sans nom ni texte libre », jamais « anonyme »", () => {
    expect(fr["measure.text"]).toMatch(/pseudonyme, sans nom ni texte libre/);
    expect(fr["measure.switchHint"]).toMatch(/Pseudonyme, sans nom ni texte libre/);
    const measure = Object.entries(fr).filter(([k]) => k.startsWith("measure."));
    expect(measure.length).toBeGreaterThan(5);
    expect(JSON.stringify(measure).replace(/pas anonyme/g, "")).not.toMatch(/anonyme/i);
  });
});
