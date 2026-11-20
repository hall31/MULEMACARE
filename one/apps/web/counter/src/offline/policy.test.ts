import { describe, expect, it } from "vitest";
import { policy, verified } from "@/test/fixtures";
import { MAX_POLICY_AGE_HOURS, MAX_VALIDITY_MINUTES, coveredAmount, evaluateOffline, isPolicyFresh, tariffAt } from "./policy";

const now = new Date("2026-10-01T10:00:00Z");
const base = { policy, policyFetchedAt: "2026-10-01T08:00:00Z", deviceId: "d-1", identification: verified, serviceDate: "2026-10-01", now };

describe("accord provisoire hors ligne (R13)", () => {
  it("accorde en provisoire un dossier sous le seuil (48 000 FCFA < 50 000)", () => {
    const r = evaluateOffline({ ...base, selectedActs: ["CS-GEN", "NFS", "ECG"] });
    expect(r.allowed).toBe(true);
    if (!r.allowed) return;
    expect(r.quote.total_xof).toBe(48_000);
    expect(r.quote.covered_xof).toBe(38_400);
    expect(r.quote.patient_share_xof).toBe(9_600);
    expect(r.quote.items).toEqual([
      { act_code: "CS-GEN", quantity: 1 },
      { act_code: "NFS", quantity: 1 },
      { act_code: "ECG", quantity: 1 },
    ]);
  });

  it("est valable exactement la durée de la politique (2 h)", () => {
    const r = evaluateOffline({ ...base, selectedActs: ["CS-GEN"] });
    if (!r.allowed) throw new Error("attendu : accordé");
    expect(r.issuedAt).toBe("2026-10-01T10:00:00.000Z");
    expect(r.expiresAt).toBe("2026-10-01T12:00:00.000Z");
  });

  it("refuse au seuil exact (borne exclue, Q-L0-02) et au-dessus", () => {
    const atThreshold = evaluateOffline({ ...base, policy: { ...policy, threshold_xof: 48_000 }, selectedActs: ["CS-GEN", "NFS", "ECG"] });
    expect(atThreshold).toMatchObject({ allowed: false, reason: "above_threshold" });
    const above = evaluateOffline({ ...base, selectedActs: ["CS-GEN", "NFS", "ECG", "ECHO-ABD"] });
    expect(above).toMatchObject({ allowed: false, reason: "above_threshold" });
  });

  it("refuse sans politique, sans appareil enregistré ou sans identification vérifiée", () => {
    expect(evaluateOffline({ ...base, policy: null, selectedActs: ["NFS"] })).toMatchObject({ reason: "no_policy" });
    expect(evaluateOffline({ ...base, deviceId: null, selectedActs: ["NFS"] })).toMatchObject({ reason: "no_device" });
    expect(evaluateOffline({ ...base, identification: { ...verified, status: "ouverte", code_verified: false }, selectedActs: ["NFS"] })).toMatchObject({ reason: "not_verified" });
  });

  it("refuse si les droits ne sont pas ouverts", () => {
    const suspended = { ...verified, beneficiary: { ...verified.beneficiary, member_status: "suspendu" as const } };
    expect(evaluateOffline({ ...base, identification: suspended, selectedActs: ["NFS"] })).toMatchObject({ reason: "member_status" });
  });

  it("refuse un acte soumis à accord préalable ou hors barème à la date du soin", () => {
    expect(evaluateOffline({ ...base, selectedActs: ["IRM"] })).toMatchObject({ reason: "prior_approval" });
    expect(evaluateOffline({ ...base, selectedActs: ["ANCIEN"] })).toMatchObject({ reason: "unknown_act" });
    expect(evaluateOffline({ ...base, selectedActs: [] })).toMatchObject({ reason: "unknown_act" });
  });

  it("ne garde que les actes du barème en vigueur à la date du soin", () => {
    expect(tariffAt(policy, "2026-10-01").map((i) => i.act_code)).not.toContain("ANCIEN");
    expect(tariffAt(policy, "2025-06-01").map((i) => i.act_code)).toEqual(["ANCIEN"]);
  });

  it("calcule la part mutuelle en entiers (arrondi au franc le plus proche)", () => {
    expect(coveredAmount(48_000, 8000)).toBe(38_400);
    expect(coveredAmount(12_345, 7000)).toBe(8_642);
    expect(Number.isInteger(coveredAmount(99_999, 3333))).toBe(true);
  });
  it("plafonne la validité à 120 min même si la politique en annonce davantage", () => {
    expect(MAX_VALIDITY_MINUTES).toBe(120);
    const r = evaluateOffline({ ...base, policy: { ...policy, validity_minutes: 600 }, selectedActs: ["CS-GEN"] });
    if (!r.allowed) throw new Error("attendu : accordé");
    expect(r.expiresAt).toBe("2026-10-01T12:00:00.000Z");
    const shorter = evaluateOffline({ ...base, policy: { ...policy, validity_minutes: 30 }, selectedActs: ["CS-GEN"] });
    if (!shorter.allowed) throw new Error("attendu : accordé");
    expect(shorter.expiresAt).toBe("2026-10-01T10:30:00.000Z");
  });

  it(`refuse une politique en cache de plus de ${MAX_POLICY_AGE_HOURS} h (Q-L7-06)`, () => {
    const limit = new Date(now.getTime() - MAX_POLICY_AGE_HOURS * 3_600_000);
    const atLimit = evaluateOffline({ ...base, policyFetchedAt: limit.toISOString(), selectedActs: ["NFS"] });
    expect(atLimit.allowed).toBe(true);
    const stale = new Date(limit.getTime() - 1).toISOString();
    expect(evaluateOffline({ ...base, policyFetchedAt: stale, selectedActs: ["NFS"] })).toMatchObject({ allowed: false, reason: "stale_policy" });
  });

  it("refuse une politique sans date de réception, illisible ou datée dans le futur (horloge reculée)", () => {
    expect(evaluateOffline({ ...base, policyFetchedAt: null, selectedActs: ["NFS"] })).toMatchObject({ reason: "stale_policy" });
    expect(evaluateOffline({ ...base, policyFetchedAt: "pas une date", selectedActs: ["NFS"] })).toMatchObject({ reason: "stale_policy" });
    expect(evaluateOffline({ ...base, policyFetchedAt: "2026-10-01T11:00:00Z", selectedActs: ["NFS"] })).toMatchObject({ reason: "stale_policy" });
    expect(isPolicyFresh("2026-10-01T08:00:00Z", now)).toBe(true);
  });
});
