/**
 * Mesure produit de la console : chaque événement construit est conforme au schéma
 * `ProductEventRequest` du contrat (Ajv 2020-12), sans texte libre ni identifiant de personne.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { describe, expect, it, vi } from "vitest";
import { parse } from "yaml";
import { EVENT_RULES, Telemetry, buildEvent, type ProductEventRequest } from "../../src/lib/telemetry";

const here = path.dirname(fileURLToPath(import.meta.url));
const spec = parse(readFileSync(path.resolve(here, "../../../../../specs/openapi.yaml"), "utf8")) as { components: { schemas: Record<string, { enum?: string[] }> } };
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
ajv.addFormat("int64", true);
ajv.addSchema(spec, "openapi.json");
const validate = ajv.compile({ $ref: "openapi.json#/components/schemas/ProductEventRequest" });

const ctx = { surface: "console" as const, role: "gestionnaire" as const, sessionId: "0123456789abcdef0123456789abcdef" };

describe("mesure produit de la console", () => {
  it("liste blanche identique à celle du contrat", () => {
    expect(Object.keys(EVENT_RULES).sort()).toEqual([...(spec.components.schemas.ProductEventName?.enum ?? [])].sort());
  });

  it("événements de la console conformes au schéma du contrat", () => {
    const events = [
      buildEvent("palette_opened", { variant: "clavier" }, ctx),
      buildEvent("palette_opened", { variant: "bouton" }, ctx),
      buildEvent("joe_question_asked", { variant: "exemple" }, ctx),
      buildEvent("joe_question_asked", { variant: "saisie" }, ctx),
      buildEvent("onboarding_completed", { duration_ms: 95_000 }, ctx),
    ];
    for (const event of events) {
      expect(event).not.toBeNull();
      expect(validate(event), JSON.stringify(validate.errors)).toBe(true);
    }
  });

  it("durée seulement pour l'accueil terminé (CR-P2-02) : refusée sur les gestes de la palette", () => {
    expect(buildEvent("joe_question_asked", { variant: "saisie", duration_ms: 812 }, ctx)).toBeNull();
    expect(buildEvent("palette_opened", { variant: "clavier", duration_ms: 40 }, ctx)).toBeNull();
    expect(buildEvent("payment_link_created", { duration_ms: 40 }, ctx)).toBeNull();
    expect(buildEvent("onboarding_completed", { duration_ms: 3_600_000 }, ctx)).toMatchObject({ duration_ms: 3_600_000 });
    expect(buildEvent("onboarding_completed", { duration_ms: 3_600_001 }, ctx)).not.toHaveProperty("duration_ms");
  });

  it("jamais la question posée à JOE, jamais d'événement d'une autre surface", () => {
    const event = buildEvent("joe_question_asked", { variant: "saisie", ...({ question: "Combien de dossiers ?" } as object) }, ctx);
    expect(JSON.stringify(event)).not.toContain("Combien");
    expect(buildEvent("card_presented", { variant: "en_ligne" }, ctx)).toBeNull();
    expect(buildEvent("offline_banner_seen", {}, ctx)).toBeNull();
  });

  it("silencieux hors ligne puis envoyé ; désactivé : rien", async () => {
    const sent: ProductEventRequest[] = [];
    let online = false;
    const telemetry = new Telemetry({ ...ctx, isOnline: () => online, isEnabled: () => true, getToken: () => "demo.gestionnaire", send: vi.fn(async (e) => void sent.push(e)) });
    telemetry.track("palette_opened", { variant: "clavier" });
    expect(sent).toEqual([]);
    online = true;
    telemetry.flush();
    await Promise.resolve();
    expect(sent).toHaveLength(1);
    const off = new Telemetry({ ...ctx, isOnline: () => true, isEnabled: () => false, getToken: () => "x", send: vi.fn(async () => undefined) });
    off.track("palette_opened", { variant: "clavier" });
    await Promise.resolve();
    expect(sent).toHaveLength(1);
  });
});
