import "fake-indexeddb/auto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NetworkUnavailable, type ApiClient } from "@/api/client";
import type { OfflineSyncRequest, OfflineSyncResult } from "@/api/types";
import { policy, verified } from "@/test/fixtures";
import { openCounterDb, type CounterDb } from "./db";
import { evaluateOffline } from "./policy";
import { issueProvisional, listRecords, purgeConfirmed, syncPending } from "./queue";
import { exportPublicJwk, fromBase64url, generateDeviceKeys, verifySignature } from "./signing";

let db: CounterDb;
let counter = 0;

beforeEach(async () => {
  counter += 1;
  db = await openCounterDb(`test-${counter}`);
});

async function issue(keys: CryptoKeyPair, ref: string) {
  const now = new Date("2026-10-01T10:00:00Z");
  const decision = evaluateOffline({ policy, policyFetchedAt: "2026-10-01T09:00:00Z", deviceId: "d-1", identification: verified, selectedActs: ["CS-GEN", "NFS", "ECG"], serviceDate: "2026-10-01", now });
  if (!decision.allowed) throw new Error("attendu : accordé");
  return issueProvisional({ db, deviceId: "d-1", privateKey: keys.privateKey, identification: verified, decision, serviceDate: "2026-10-01", policy, newId: () => ref });
}

function fakeApi(handler: (body: OfflineSyncRequest) => Promise<OfflineSyncResult>): ApiClient {
  return { syncOffline: vi.fn(handler) } as unknown as ApiClient;
}

describe("file de synchronisation IndexedDB (R13)", () => {
  it("stocke l'accord signé, sans nom ni photo de l'adhérent", async () => {
    const keys = await generateDeviceKeys();
    const record = await issue(keys, "11111111-1111-4111-8111-111111111111");
    const [stored] = await listRecords(db);
    expect(stored?.status).toBe("en_attente");
    expect(stored?.input).toMatchObject({
      offline_ref: "11111111-1111-4111-8111-111111111111",
      member_number: "MC-00000042",
      beneficiary_id: verified.beneficiary.person_id,
      total_xof: 48_000,
      covered_xof: 38_400,
      issued_at: "2026-10-01T10:00:00.000Z",
      expires_at: "2026-10-01T12:00:00.000Z",
    });
    expect(JSON.stringify(stored)).not.toContain("Aya");
    const jwk = await exportPublicJwk(keys.publicKey);
    expect(await verifySignature(jwk, record.input.signed_payload, record.input.signature)).toBe(true);
    const signed = JSON.parse(new TextDecoder().decode(fromBase64url(record.input.signed_payload))) as Record<string, unknown>;
    expect(signed).toMatchObject({ device_id: "d-1", offline_ref: record.input.offline_ref, total_xof: 48_000, covered_xof: 38_400, expires_at: record.input.expires_at });
  });

  it("synchronise au retour du réseau et marque l'accord confirmé", async () => {
    const keys = await generateDeviceKeys();
    await issue(keys, "22222222-2222-4222-8222-222222222222");
    const api = fakeApi(async (body) => ({
      results: body.authorizations.map((a) => ({ offline_ref: a.offline_ref, outcome: "confirmee", reason_code: null, claim_id: "c-1", authorization_id: "a-1" })),
    }));
    const report = await syncPending({ db, api, deviceId: "d-1" });
    expect(report).toEqual({ sent: 1, confirmed: 1, rejected: 0 });
    expect(api.syncOffline).toHaveBeenCalledWith(expect.objectContaining({ device_id: "d-1", authorizations: [expect.objectContaining({ offline_ref: "22222222-2222-4222-8222-222222222222" })] }));
    const [stored] = await listRecords(db);
    expect(stored).toMatchObject({ status: "confirmee", claim_id: "c-1", authorization_id: "a-1" });
    await purgeConfirmed(db);
    expect(await listRecords(db)).toEqual([]);
  });

  it("garde l'accord en attente si le réseau est encore coupé, sans doublon au nouvel essai", async () => {
    const keys = await generateDeviceKeys();
    await issue(keys, "33333333-3333-4333-8333-333333333333");
    const down = fakeApi(async () => {
      throw new NetworkUnavailable();
    });
    await expect(syncPending({ db, api: down, deviceId: "d-1" })).rejects.toBeInstanceOf(NetworkUnavailable);
    expect((await listRecords(db)).map((r) => r.status)).toEqual(["en_attente"]);
    const up = fakeApi(async (body) => ({ results: body.authorizations.map((a) => ({ offline_ref: a.offline_ref, outcome: "confirmee" })) }));
    await syncPending({ db, api: up, deviceId: "d-1" });
    await syncPending({ db, api: up, deviceId: "d-1" });
    expect(up.syncOffline).toHaveBeenCalledTimes(1);
    expect(await listRecords(db)).toHaveLength(1);
  });

  it("enregistre le refus de la mutuelle avec son code stable", async () => {
    const keys = await generateDeviceKeys();
    await issue(keys, "44444444-4444-4444-8444-444444444444");
    const api = fakeApi(async (body) => ({ results: body.authorizations.map((a) => ({ offline_ref: a.offline_ref, outcome: "rejetee", reason_code: "OFF-01" })) }));
    expect(await syncPending({ db, api, deviceId: "d-1" })).toEqual({ sent: 1, confirmed: 0, rejected: 1 });
    expect(await listRecords(db)).toEqual([expect.objectContaining({ status: "rejetee", reason_code: "OFF-01" })]);
  });
});
