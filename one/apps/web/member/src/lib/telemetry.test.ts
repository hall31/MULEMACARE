import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { parse } from "yaml";
import { STORAGE_PREFIX } from "./device-data";
import { MEASURE_CHOICE_KEY } from "./measure-consent";
import { EVENT_RULES, TELEMETRY_KEY, Telemetry, buildEvent, newSessionId, type ProductEventRequest } from "./telemetry";

const here = path.dirname(fileURLToPath(import.meta.url));
const spec = parse(readFileSync(path.join(here, "../../../../../specs/openapi.yaml"), "utf8")) as {
  components: { schemas: Record<string, { enum?: string[]; properties?: Record<string, unknown>; required?: string[] }> };
};

const ctx = { surface: "espace_adherent" as const, role: "adherent" as const, sessionId: "0123456789abcdef0123456789abcdef" };

function harness(over: { online?: boolean; enabled?: boolean; token?: string | null; fail?: boolean } = {}) {
  const sent: ProductEventRequest[] = [];
  let online = over.online ?? true;
  const send = vi.fn(async (event: ProductEventRequest) => {
    if (over.fail) throw new Error("réseau");
    sent.push(event);
  });
  const telemetry = new Telemetry({ surface: "espace_adherent", role: "adherent", send, isOnline: () => online, isEnabled: () => over.enabled ?? true, getToken: () => (over.token === undefined ? "jeton" : over.token) });
  return { telemetry, sent, send, goOnline: () => { online = true; telemetry.flush(); } };
}

describe("liste blanche du contrat (ProductEventName, recordProductEvent)", () => {
  it("chaque événement du contrat a une règle, et aucun autre", () => {
    expect(Object.keys(EVENT_RULES).sort()).toEqual([...(spec.components.schemas.ProductEventName?.enum ?? [])].sort());
  });

  it("le corps n'a que les champs du contrat : ni texte libre, ni identifiant de personne", () => {
    const allowed = Object.keys(spec.components.schemas.ProductEventRequest?.properties ?? {}).sort();
    expect(allowed).toEqual(["duration_ms", "name", "role", "session_id", "step", "surface", "variant"]);
    const event = buildEvent("card_presented", { variant: "en_ligne", ...({ question: "texte libre", member_number: "MC-00928194" } as object) }, ctx);
    expect(Object.keys(event ?? {}).sort()).toEqual(["name", "role", "session_id", "surface", "variant"]);
  });
});

describe("règles par événement (miroir de apps/api/metrics/catalog.py)", () => {
  it("variante exigée et bornée ; événement d'une autre surface refusé", () => {
    expect(buildEvent("card_presented", {}, ctx)).toBeNull();
    expect(buildEvent("card_presented", { variant: "clavier" }, ctx)).toBeNull();
    expect(buildEvent("card_presented", { variant: "hors_ligne" }, ctx)).toMatchObject({ name: "card_presented", variant: "hors_ligne" });
    expect(buildEvent("palette_opened", { variant: "clavier" }, ctx)).toBeNull();
    expect(buildEvent("counter_decision_shown", { variant: "accordee", duration_ms: 3000 }, ctx)).toBeNull();
    expect(buildEvent("offline_banner_seen", { variant: "in_app" }, ctx)).toBeNull();
  });

  it("étape exigée pour onboarding_step (1 à 20), interdite ailleurs ; durée entière bornée", () => {
    expect(buildEvent("onboarding_step", {}, ctx)).toBeNull();
    expect(buildEvent("onboarding_step", { step: 21 }, ctx)).toBeNull();
    expect(buildEvent("onboarding_step", { step: 2 }, ctx)).toMatchObject({ step: 2 });
    expect(buildEvent("onboarding_started", { step: 1 }, ctx)).toBeNull();
    expect(buildEvent("onboarding_completed", { duration_ms: 61_234.7 }, ctx)).toMatchObject({ duration_ms: 61_235 });
    // Durée hors borne (négative, au-delà d'une heure) : l'accueil terminé compte, sans la durée.
    for (const duration_ms of [-1, 3_600_001, Number.NaN]) {
      const event = buildEvent("onboarding_completed", { duration_ms }, ctx);
      expect(event).toMatchObject({ name: "onboarding_completed" });
      expect(event).not.toHaveProperty("duration_ms");
    }
    expect(buildEvent("onboarding_completed", { duration_ms: 3_600_000 }, ctx)).toMatchObject({ duration_ms: 3_600_000 });
  });

  it("durée refusée ailleurs que sur les deux événements du contrat (CR-P2-02, 422 sinon)", () => {
    expect(buildEvent("claim_tracking_viewed", { duration_ms: 1200 }, ctx)).toBeNull();
    expect(buildEvent("card_presented", { variant: "en_ligne", duration_ms: 80 }, ctx)).toBeNull();
    expect(buildEvent("onboarding_step", { step: 2, duration_ms: 80 }, ctx)).toBeNull();
    expect(buildEvent("onboarding_started", { duration_ms: 0 }, ctx)).toBeNull();
  });
});

describe("identifiant de session", () => {
  it("aléatoire, exactement 32 caractères hexadécimaux minuscules (CR-P2-02), jamais que des chiffres, renouvelé", () => {
    const a = newSessionId();
    expect(a).toMatch(/^[0-9a-f]{32}$/);
    expect(a).not.toMatch(/^[0-9]+$/);
    expect(newSessionId()).not.toBe(a);
    expect(newSessionId(() => new Uint8Array(16))).toMatch(/^(?![0-9]+$)[0-9a-f]{32}$/);
  });
});

describe("envoi : non bloquant, silencieux hors ligne, désactivable", () => {
  it("en ligne : envoyé une fois, avec le rôle, la surface et la session de l'onglet", async () => {
    const { telemetry, sent } = harness();
    telemetry.track("claim_tracking_viewed");
    await Promise.resolve();
    expect(sent).toEqual([expect.objectContaining({ name: "claim_tracking_viewed", surface: "espace_adherent", role: "adherent" })]);
    expect(sent[0]?.session_id).toBe(telemetry.sessionId);
  });

  it("hors ligne : rien ne part, gardé en mémoire (20 au plus) puis envoyé au retour du réseau", async () => {
    const { telemetry, sent, goOnline } = harness({ online: false });
    telemetry.track("offline_banner_seen");
    for (let i = 0; i < 30; i += 1) telemetry.track("onboarding_started");
    expect(sent).toEqual([]);
    goOnline();
    await Promise.resolve();
    expect(sent).toHaveLength(20);
    expect(sent[0]?.name).toBe("offline_banner_seen");
  });

  it("erreur d'envoi : jamais d'exception, jamais de nouvel essai en boucle", async () => {
    const { telemetry, send } = harness({ fail: true });
    expect(() => telemetry.track("onboarding_started")).not.toThrow();
    await Promise.resolve();
    expect(send).toHaveBeenCalledTimes(1);
  });

  it("désactivée, sans jeton, ou événement refusé par les règles : rien n'est envoyé", async () => {
    for (const h of [harness({ enabled: false }), harness({ token: null })]) {
      h.telemetry.track("onboarding_started");
      await Promise.resolve();
      expect(h.send).not.toHaveBeenCalled();
    }
    const h = harness();
    h.telemetry.track("palette_opened", { variant: "clavier" });
    await Promise.resolve();
    expect(h.send).not.toHaveBeenCalled();
  });

  it("l'ancien interrupteur reste sous le préfixe (effacé à la déconnexion) ; le choix, lui, n'y est pas", () => {
    expect(TELEMETRY_KEY.startsWith(STORAGE_PREFIX)).toBe(true);
    expect(MEASURE_CHOICE_KEY.startsWith(STORAGE_PREFIX)).toBe(false);
  });
});
