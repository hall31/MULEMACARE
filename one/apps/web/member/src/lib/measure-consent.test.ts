import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import fr from "../i18n/fr.json";
import { STORAGE_PREFIX, purgeDeviceData, type ScannableStore } from "./device-data";
import { MEASURE_CHOICE_KEY, measureAllowed, readMeasureChoice, writeMeasureChoice } from "./measure-consent";
import { TELEMETRY_KEY, Telemetry, type ProductEventRequest } from "./telemetry";

function memoryStore(initial: Record<string, string> = {}): ScannableStore & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial));
  return {
    data,
    get length() {
      return data.size;
    },
    key: (i) => [...data.keys()][i] ?? null,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

describe("consentement à la mesure (pseudonyme : désactivée tant que l'adhérent n'a pas choisi)", () => {
  it("aucun choix : pas de mesure ; seul un accord explicite l'active ; réversible", () => {
    const store = memoryStore();
    expect(readMeasureChoice(store)).toBeNull();
    expect(measureAllowed(readMeasureChoice(store), false)).toBe(false);
    writeMeasureChoice(store, "granted");
    expect(measureAllowed(readMeasureChoice(store), false)).toBe(true);
    writeMeasureChoice(store, "refused");
    expect(measureAllowed(readMeasureChoice(store), false)).toBe(false);
  });

  it("instance coupée : jamais de mesure ; valeur illisible : pas de choix ; ancien « off » : refus", () => {
    expect(measureAllowed("granted", true)).toBe(false);
    expect(readMeasureChoice(memoryStore({ [MEASURE_CHOICE_KEY]: "{x" }))).toBeNull();
    expect(readMeasureChoice(memoryStore({ [MEASURE_CHOICE_KEY]: JSON.stringify({ v: 1, choice: "oui" }) }))).toBeNull();
    expect(readMeasureChoice(memoryStore({ [TELEMETRY_KEY]: "off" }))).toBe("refused");
  });

  it("le choix survit à la déconnexion (hors du préfixe effacé), sans donnée de l'adhérent", async () => {
    expect(MEASURE_CHOICE_KEY.startsWith(STORAGE_PREFIX)).toBe(false);
    const store = memoryStore({ [`${STORAGE_PREFIX}derniere-carte`]: "{}" });
    writeMeasureChoice(store, "refused");
    await purgeDeviceData({ store, caches: null, queryClient: new QueryClient() });
    expect(readMeasureChoice(store)).toBe("refused");
    expect(JSON.parse(store.data.get(MEASURE_CHOICE_KEY) ?? "null")).toEqual({ v: 1, choice: "refused" });
    expect(store.data.has(`${STORAGE_PREFIX}derniere-carte`)).toBe(false);
  });

  it("un ancien refus (sous le préfixe) est repris dans la clé qui survit, avant la purge", async () => {
    const store = memoryStore({ [TELEMETRY_KEY]: "off" });
    writeMeasureChoice(store, readMeasureChoice(store) ?? "refused");
    await purgeDeviceData({ store, caches: null, queryClient: new QueryClient() });
    expect(readMeasureChoice(store)).toBe("refused");
  });
});

describe("envoi selon le choix", () => {
  const options = { surface: "espace_adherent" as const, role: "adherent" as const, getToken: () => "jeton" };

  it("désactivée : l'envoi n'est jamais appelé ; refus pendant une coupure : la file est oubliée", async () => {
    const send = vi.fn(async () => undefined);
    const off = new Telemetry({ ...options, isOnline: () => true, isEnabled: () => false, send });
    off.track("claim_tracking_viewed");
    off.flush();
    let enabled = true;
    let online = false;
    const sent: ProductEventRequest[] = [];
    const t = new Telemetry({ ...options, isOnline: () => online, isEnabled: () => enabled, send: async (e) => void sent.push(e) });
    t.track("claim_tracking_viewed");
    enabled = false;
    online = true;
    t.flush();
    enabled = true;
    t.flush();
    await Promise.resolve();
    expect(send).not.toHaveBeenCalled();
    expect(sent).toEqual([]);
  });
});

describe("libellés honnêtes", () => {
  it("« mesure pseudonyme, sans nom ni texte libre », jamais « anonyme »", () => {
    expect(fr["measure.text"]).toMatch(/pseudonyme, sans nom ni texte libre/);
    expect(fr["notif.prefs.measure"]).toMatch(/pseudonyme, sans nom ni texte libre/);
    const measure = Object.entries(fr).filter(([k]) => k.startsWith("measure.") || k.startsWith("notif.prefs.measure"));
    expect(measure.length).toBeGreaterThan(6);
    expect(JSON.stringify(measure).replace(/pas anonyme/g, "")).not.toMatch(/anonyme/i);
  });
});
