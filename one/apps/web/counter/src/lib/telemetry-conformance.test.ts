import { describe, expect, it, vi } from "vitest";
import { CONTRACT_DURATIONS, contractDurationProperty, contractProblems, spec } from "@/test/contract-event";
import { EVENT_RULES, Telemetry, newSessionId, type EventProps, type ProductEventName, type ProductEventRequest, type ProductEventVariant } from "./telemetry";

/**
 * Conformité au contrat de CHAQUE événement que le client peut émettre (CR-P2-02) : toutes les
 * combinaisons de propriétés, admises ou non, passent par une vraie instance `Telemetry` (identifiant
 * de session tiré par `crypto.getRandomValues`) ; tout ce qui part vers l'API est jugé contre
 * `ProductEventRequest` de `specs/openapi.yaml` et les règles de durée que l'API applique en 422.
 */
const SURFACE = "comptoir" as const;
const ROLE = "clinique" as const;

const VARIANTS = (spec.components.schemas.ProductEventVariant?.enum ?? []) as ProductEventVariant[];
const STEPS = [undefined, 0, 1, 7, 20, 21, 2.5];
const DURATIONS = [undefined, 0, 1, 4_200.4, 299_999.6, 300_000, 300_001, 3_600_000, 3_600_001, 86_400_000, -1, Number.NaN, Number.POSITIVE_INFINITY];

function everyAttempt(): Array<[ProductEventName, EventProps]> {
  const attempts: Array<[ProductEventName, EventProps]> = [];
  for (const name of Object.keys(EVENT_RULES) as ProductEventName[])
    for (const variant of [undefined, ...VARIANTS])
      for (const step of STEPS)
        for (const duration_ms of DURATIONS)
          attempts.push([name, { ...(variant !== undefined ? { variant } : {}), ...(step !== undefined ? { step } : {}), ...(duration_ms !== undefined ? { duration_ms } : {}) }]);
  return attempts;
}

function emitted(): ProductEventRequest[] {
  const sent: ProductEventRequest[] = [];
  const telemetry = new Telemetry({ surface: SURFACE, role: ROLE, isOnline: () => true, isEnabled: () => true, getToken: () => "jeton", send: async (event) => void sent.push(event) });
  for (const [name, props] of everyAttempt()) telemetry.track(name, props);
  return sent;
}

describe("le juge suit le contrat (specs/openapi.yaml)", () => {
  it("identifiant de session et durées : ce que dit ProductEventRequest", () => {
    expect(spec.components.schemas.ProductEventRequest?.properties?.session_id?.pattern).toBe("^[0-9a-f]{32}$");
    const duration = contractDurationProperty();
    expect(duration.maximum).toBe(Math.max(...Object.values(CONTRACT_DURATIONS).map((r) => r.max)));
    expect(duration.description).toContain("counter_decision_shown (obligatoire, 300 000 au plus)");
    expect(duration.description).toContain("onboarding_completed (facultative)");
    expect(duration.description).toContain("refusée ailleurs");
  });

  it("refuse ce que l'API refuse (le test ne peut pas passer à vide)", () => {
    const base = { name: "onboarding_started", surface: SURFACE, role: ROLE, session_id: "0123456789abcdef0123456789abcdef" };
    expect(contractProblems(base)).toEqual([]);
    expect(contractProblems({ ...base, session_id: "AbCdEfGhIjKlMnOpQrStUv" })).not.toEqual([]);
    expect(contractProblems({ ...base, session_id: "0123456789ABCDEF0123456789ABCDEF" })).not.toEqual([]);
    expect(contractProblems({ ...base, session_id: "01234567890123456789012345678901" })).not.toEqual([]);
    expect(contractProblems({ ...base, duration_ms: 10 })).not.toEqual([]);
    expect(contractProblems({ ...base, name: "counter_decision_shown", variant: "accordee" })).not.toEqual([]);
    expect(contractProblems({ ...base, name: "counter_decision_shown", variant: "accordee", duration_ms: 300_001 })).not.toEqual([]);
    expect(contractProblems({ ...base, name: "onboarding_completed", duration_ms: 3_600_001 })).not.toEqual([]);
    expect(contractProblems({ ...base, question: "texte libre" })).not.toEqual([]);
  });
});

describe(`chaque événement émis par la surface ${SURFACE} est conforme`, () => {
  const sent = emitted();

  it("aucun corps envoyé n'est refusable par l'API", () => {
    expect(sent.length).toBeGreaterThan(0);
    const refused = sent.map((event) => [event, contractProblems(event)] as const).filter(([, problems]) => problems.length > 0);
    expect(refused.slice(0, 5)).toEqual([]);
  });

  it("chaque événement admis sur cette surface peut partir", () => {
    const admitted = (Object.keys(EVENT_RULES) as ProductEventName[]).filter((name) => EVENT_RULES[name].surfaces.includes(SURFACE));
    expect([...new Set(sent.map((e) => e.name))].sort()).toEqual(admitted.sort());
  });

  it("duration_ms seulement pour les deux événements autorisés, et toujours pour la décision au comptoir", () => {
    const withDuration = new Set(sent.filter((e) => e.duration_ms !== undefined).map((e) => e.name));
    for (const name of withDuration) expect(Object.keys(CONTRACT_DURATIONS)).toContain(name);
    for (const event of sent.filter((e) => e.name === "counter_decision_shown")) expect(event.duration_ms).toEqual(expect.any(Number));
    const completed = sent.filter((e) => e.name === "onboarding_completed");
    expect(completed.some((e) => e.duration_ms !== undefined)).toBe(true);
    expect(completed.some((e) => e.duration_ms === undefined)).toBe(true);
  });
});

describe("identifiant de session (CR-P2-02)", () => {
  it("16 octets de crypto.getRandomValues, 32 caractères hexadécimaux minuscules, renouvelé", () => {
    const spy = vi.spyOn(globalThis.crypto, "getRandomValues");
    const ids = Array.from({ length: 500 }, () => newSessionId());
    expect(spy).toHaveBeenCalledTimes(500);
    for (const [array] of spy.mock.calls) expect((array as Uint8Array).length).toBe(16);
    for (const id of ids) expect(id).toMatch(/^[0-9a-f]{32}$/);
    expect(new Set(ids).size).toBe(ids.length);
    spy.mockRestore();
  });

  it("octets rendus tels quels en hexadécimal ; jamais fait que de chiffres", () => {
    expect(newSessionId(() => Uint8Array.from({ length: 16 }, (_, i) => i * 17))).toBe("00112233445566778899aabbccddeeff");
    const zeros = newSessionId(() => new Uint8Array(16));
    expect(zeros).toMatch(/^[0-9a-f]{32}$/);
    expect(zeros).not.toMatch(/^[0-9]+$/);
  });

  it("l'instance porte un identifiant conforme", () => {
    const telemetry = new Telemetry({ surface: SURFACE, role: ROLE, isOnline: () => true, isEnabled: () => true, getToken: () => null, send: async () => undefined });
    expect(telemetry.sessionId).toMatch(/^[0-9a-f]{32}$/);
  });
});
