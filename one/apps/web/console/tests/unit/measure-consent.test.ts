// @vitest-environment jsdom
/**
 * Consentement à la mesure produit (droit ivoirien et sénégalais des données personnelles : un
 * identifiant de session est un pseudonyme, pas un anonymat). Désactivée tant que la personne n'a
 * pas choisi ; choix explicite, réversible, gardé sur le navigateur sans donnée personnelle.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import fr from "../../src/i18n/fr.json" with { type: "json" };
import { MEASURE_CHOICE_KEY, readMeasureChoice, setMeasureChoice } from "../../src/lib/measure-consent";
import { TELEMETRY_KEY, Telemetry, telemetryEnabled, type ProductEventRequest } from "../../src/lib/telemetry";

const ctx = { surface: "console" as const, role: "medecin_conseil" as const };

afterEach(() => {
  window.localStorage.clear();
  vi.unstubAllEnvs();
});

describe("choix de la personne", () => {
  it("aucun choix : mesure désactivée (rien n'est envoyé par défaut)", () => {
    expect(readMeasureChoice()).toBeNull();
    expect(telemetryEnabled()).toBe(false);
  });

  it("accepté : activée ; refusé ensuite : désactivée (réversible)", () => {
    setMeasureChoice("granted");
    expect(telemetryEnabled()).toBe(true);
    setMeasureChoice("refused");
    expect(readMeasureChoice()).toBe("refused");
    expect(telemetryEnabled()).toBe(false);
  });

  it("instance coupée : désactivée même si la personne a accepté", () => {
    setMeasureChoice("granted");
    vi.stubEnv("NEXT_PUBLIC_MULEMA_TELEMETRY", "off");
    expect(telemetryEnabled()).toBe(false);
  });

  it("valeur illisible ou inconnue : pas de choix (donc rien n'est envoyé)", () => {
    window.localStorage.setItem(MEASURE_CHOICE_KEY, "{x");
    expect(readMeasureChoice()).toBeNull();
    window.localStorage.setItem(MEASURE_CHOICE_KEY, JSON.stringify({ v: 1, choice: "peut-etre" }));
    expect(readMeasureChoice()).toBeNull();
    expect(telemetryEnabled()).toBe(false);
  });

  it("un refus donné avec l'ancien interrupteur reste un refus", () => {
    window.localStorage.setItem(TELEMETRY_KEY, "off");
    expect(readMeasureChoice()).toBe("refused");
  });

  it("ce qui est gardé : le choix et sa version, rien d'autre", () => {
    setMeasureChoice("granted");
    expect(JSON.parse(window.localStorage.getItem(MEASURE_CHOICE_KEY) ?? "null")).toEqual({ v: 1, choice: "granted" });
  });
});

describe("envoi", () => {
  function harness(enabled: () => boolean, online: () => boolean = () => true) {
    const sent: ProductEventRequest[] = [];
    const send = vi.fn(async (event: ProductEventRequest) => void sent.push(event));
    const telemetry = new Telemetry({ ...ctx, send, isOnline: online, isEnabled: enabled, getToken: () => "demo.medecin_conseil" });
    return { telemetry, send, sent };
  }

  it("désactivée : l'envoi n'est jamais appelé", async () => {
    const { telemetry, send } = harness(() => false);
    telemetry.track("palette_opened", { variant: "clavier" });
    telemetry.flush();
    await Promise.resolve();
    expect(send).not.toHaveBeenCalled();
  });

  it("refus pendant une coupure : ce qui attendait est oublié, rien ne part au retour du réseau", async () => {
    let enabled = true;
    let online = false;
    const { telemetry, send } = harness(() => enabled, () => online);
    telemetry.track("palette_opened", { variant: "bouton" });
    enabled = false;
    online = true;
    telemetry.flush();
    enabled = true;
    telemetry.flush();
    await Promise.resolve();
    expect(send).not.toHaveBeenCalled();
  });

  it("activée : envoyé", async () => {
    const { telemetry, sent } = harness(() => true);
    telemetry.track("palette_opened", { variant: "clavier" });
    await Promise.resolve();
    expect(sent).toHaveLength(1);
  });
});

describe("libellés honnêtes", () => {
  it("la mesure d'usage est dite pseudonyme, sans nom ni texte libre ; jamais « anonyme »", () => {
    const measure = fr.measure;
    expect(measure.banner.text).toMatch(/pseudonyme/);
    expect(measure.banner.text).toMatch(/sans nom ni texte libre/);
    // « pseudonyme, pas anonyme » est la seule mention admise.
    expect(JSON.stringify(measure).replace(/pas anonyme/g, "")).not.toMatch(/anonyme/i);
    expect(measure.details.pseudonymous).toMatch(/pseudonyme, pas anonyme/);
    expect(fr.metrics.intro).not.toMatch(/usage anonymes?/i);
  });
});
