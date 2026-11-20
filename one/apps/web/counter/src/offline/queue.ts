import type { ApiClient } from "@/api/client";
import type { Identification, OfflineAuthorizationInput, OfflinePolicy } from "@/api/types";
import type { CounterDb, QueueRecord } from "./db";
import type { OfflineEvaluation } from "./policy";
import { signPayload } from "./signing";

type Allowed = Extract<OfflineEvaluation, { allowed: true }>;

export interface IssueProvisionalInput {
  db: CounterDb;
  deviceId: string;
  privateKey: CryptoKey;
  identification: Identification;
  decision: Allowed;
  serviceDate: string;
  policy: OfflinePolicy;
  newId?: () => string;
}

/** Signe l'accord provisoire sur l'appareil et le place dans la file de synchronisation. */
export async function issueProvisional(input: IssueProvisionalInput): Promise<QueueRecord> {
  const { db, deviceId, privateKey, identification, decision, serviceDate, policy } = input;
  const offlineRef = (input.newId ?? (() => crypto.randomUUID()))();
  const { quote } = decision;
  const content = {
    v: 1,
    offline_ref: offlineRef,
    device_id: deviceId,
    identification_id: identification.id,
    member_number: identification.beneficiary.member_number,
    beneficiary_id: identification.beneficiary.person_id,
    service_date: serviceDate,
    items: quote.items.map((i) => ({ act_code: i.act_code, quantity: i.quantity ?? 1 })),
    total_xof: quote.total_xof,
    covered_xof: quote.covered_xof,
    currency: policy.currency,
    issued_at: decision.issuedAt,
    expires_at: decision.expiresAt,
    rules: policy.rules.map((r) => ({ code: r.code, version: r.version })),
  };
  const signed = await signPayload(privateKey, content);
  const authorization: OfflineAuthorizationInput = {
    offline_ref: offlineRef,
    member_number: content.member_number,
    beneficiary_id: content.beneficiary_id,
    service_date: serviceDate,
    items: content.items,
    total_xof: quote.total_xof,
    covered_xof: quote.covered_xof,
    issued_at: decision.issuedAt,
    expires_at: decision.expiresAt,
    signed_payload: signed.signed_payload,
    signature: signed.signature,
  };
  const record: QueueRecord = {
    offline_ref: offlineRef,
    input: authorization,
    status: "en_attente",
    reason_code: null,
    claim_id: null,
    authorization_id: null,
    created_at: decision.issuedAt,
    synced_at: null,
  };
  await db.put("queue", record);
  return record;
}

export async function listRecords(db: CounterDb): Promise<QueueRecord[]> {
  const records = await db.all("queue");
  return records.sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export interface SyncReport {
  sent: number;
  confirmed: number;
  rejected: number;
}

const MAX_BATCH = 200;

/**
 * Envoie les accords en attente (idempotent côté serveur par device_id + offline_ref).
 * Une erreur réseau remonte telle quelle : les accords restent en attente pour le prochain essai.
 */
export async function syncPending({ db, api, deviceId, now = () => new Date() }: { db: CounterDb; api: ApiClient; deviceId: string; now?: () => Date }): Promise<SyncReport> {
  const pending = (await listRecords(db)).filter((r) => r.status === "en_attente").slice(0, MAX_BATCH);
  if (pending.length === 0) return { sent: 0, confirmed: 0, rejected: 0 };
  const result = await api.syncOffline({ device_id: deviceId, authorizations: pending.map((r) => r.input) });
  const byRef = new Map(pending.map((r) => [r.offline_ref, r]));
  const report: SyncReport = { sent: pending.length, confirmed: 0, rejected: 0 };
  const syncedAt = now().toISOString();
  for (const item of result.results) {
    const record = byRef.get(item.offline_ref);
    if (!record) continue;
    const confirmed = item.outcome === "confirmee";
    if (confirmed) report.confirmed += 1;
    else report.rejected += 1;
    await db.put("queue", {
      ...record,
      status: confirmed ? "confirmee" : "rejetee",
      reason_code: item.reason_code ?? null,
      claim_id: item.claim_id ?? null,
      authorization_id: item.authorization_id ?? null,
      synced_at: syncedAt,
    });
  }
  return report;
}

/** Les accords confirmés n'ont plus rien à faire sur l'appareil (minimisation des données). */
export async function purgeConfirmed(db: CounterDb): Promise<void> {
  for (const record of await db.all("queue")) {
    if (record.status === "confirmee") await db.delete("queue", record.offline_ref);
  }
}
