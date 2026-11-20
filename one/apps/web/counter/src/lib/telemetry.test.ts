import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import { EVENT_RULES, Telemetry, buildEvent, decisionVariant, type ProductEventRequest } from "./telemetry";

const here = path.dirname(fileURLToPath(import.meta.url));
const spec = readFileSync(path.join(here, "../../../../../specs/openapi.yaml"), "utf8");

/** Énumération `ProductEventName` du contrat (lecture du YAML sans dépendance). */
function contractEventNames(): string[] {
  const block = spec.slice(spec.indexOf("    ProductEventName:"));
  const body = block.slice(block.indexOf("enum:") + 5, block.indexOf("    ProductSurface:"));
  return [...body.matchAll(/^\s+- ([a-z_]+)$/gm)].map((m) => m[1] ?? "");
}

const ctx = { surface: "comptoir" as const, role: "clinique" as const, sessionId: "0123456789abcdef0123456789abcdef" };

describe("mesure produit du comptoir", () => {
  it("liste blanche identique à celle du contrat", () => {
    expect(Object.keys(EVENT_RULES).sort()).toEqual(contractEventNames().sort());
  });

  it("counter_decision_shown : variante et durée exigées (scan → écran de décision)", () => {
    expect(buildEvent("counter_decision_shown", { variant: "accordee" }, ctx)).toBeNull();
    expect(buildEvent("counter_decision_shown", { variant: "accordee", duration_ms: 4200.4 }, ctx)).toEqual({ name: "counter_decision_shown", surface: "comptoir", role: "clinique", session_id: ctx.sessionId, variant: "accordee", duration_ms: 4200 });
    expect(buildEvent("card_presented", { variant: "en_ligne" }, ctx)).toBeNull();
    expect(buildEvent("offline_banner_seen", {}, ctx)).toMatchObject({ name: "offline_banner_seen", surface: "comptoir", role: "clinique" });
  });

  it("durée (CR-P2-02) : exigée et 5 min au plus pour la décision, facultative et 1 h au plus pour l'accueil, refusée ailleurs", () => {
    const decision = (duration_ms: number) => buildEvent("counter_decision_shown", { variant: "revue", duration_ms }, ctx);
    expect(decision(300_000)).toMatchObject({ duration_ms: 300_000 });
    expect(decision(300_000.6)).toBeNull();
    expect(decision(300_001)).toBeNull();
    expect(decision(-1)).toBeNull();
    expect(decision(Number.NaN)).toBeNull();
    expect(buildEvent("onboarding_completed", {}, ctx)).not.toHaveProperty("duration_ms");
    expect(buildEvent("onboarding_completed", { duration_ms: 3_600_000 }, ctx)).toMatchObject({ duration_ms: 3_600_000 });
    // Accueil terminé mais durée hors borne : l'achèvement compte, la durée n'est pas envoyée.
    const late = buildEvent("onboarding_completed", { duration_ms: 3_600_001 }, ctx);
    expect(late).toMatchObject({ name: "onboarding_completed" });
    expect(late).not.toHaveProperty("duration_ms");
    expect(buildEvent("offline_banner_seen", { duration_ms: 12 }, ctx)).toBeNull();
    expect(buildEvent("onboarding_step", { step: 1, duration_ms: 12 }, ctx)).toBeNull();
    expect(buildEvent("onboarding_started", { duration_ms: 0 }, ctx)).toBeNull();
  });

  it("variante de la décision affichée", () => {
    expect(decisionVariant({ kind: "online", status: "accordee_auto" })).toBe("accordee");
    expect(decisionVariant({ kind: "online", status: "en_revue" })).toBe("revue");
    expect(decisionVariant({ kind: "online", status: "refusee" })).toBe("refusee");
    expect(decisionVariant({ kind: "provisional" })).toBe("accordee");
    expect(decisionVariant({ kind: "offline_refused" })).toBeNull();
  });

  it("silencieux hors ligne, envoyé au retour, jamais bloquant", async () => {
    const sent: ProductEventRequest[] = [];
    let online = false;
    const t = new Telemetry({ surface: "comptoir", role: "clinique", isOnline: () => online, isEnabled: () => true, getToken: () => "jeton", send: vi.fn(async (e) => void sent.push(e)) });
    t.track("offline_banner_seen");
    expect(sent).toEqual([]);
    online = true;
    t.flush();
    await Promise.resolve();
    expect(sent.map((e) => e.name)).toEqual(["offline_banner_seen"]);
    const failing = new Telemetry({ surface: "comptoir", role: "clinique", isOnline: () => true, isEnabled: () => true, getToken: () => "jeton", send: async () => Promise.reject(new Error("x")) });
    expect(() => failing.track("onboarding_started")).not.toThrow();
  });
});
