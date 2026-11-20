/**
 * Le serveur de mocks applique les règles d'accès du contrat, pour que la console soit
 * testée contre le même comportement que l'API réelle (L1/L5) :
 * R6 — motif médical réservé au médecin-conseil et journalisé ; décision humaine seulement sur un dossier en revue.
 */
import { describe, expect, it } from "vitest";
import { API_BASE_URL } from "../../src/lib/config";
import { demoToken, type DemoRole } from "../../src/lib/session";
import { AUTO_CLAIM, REVIEW_CLAIM, medicalReasonFor } from "../../src/mocks/fixtures";
import { auditEvents } from "../../src/mocks/store";

function api(role: DemoRole, url: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${API_BASE_URL}${url}`, {
    ...init,
    headers: { Authorization: `Bearer ${demoToken(role)}`, "Content-Type": "application/json", ...init.headers },
  });
}

describe("motif médical (R6)", () => {
  it("aucune réponse de liste ou de détail ne contient le motif", async () => {
    const reason = medicalReasonFor(REVIEW_CLAIM.id);
    for (const role of ["gestionnaire", "medecin_conseil"] as const) {
      const list = await (await api(role, "/v1/claims")).text();
      const detail = await (await api(role, `/v1/claims/${REVIEW_CLAIM.id}`)).text();
      expect(list).not.toContain(reason);
      expect(detail).not.toContain(reason);
    }
  });

  it("gestionnaire : 403 SEC-01, aucune trace de lecture", async () => {
    const res = await api("gestionnaire", `/v1/claims/${REVIEW_CLAIM.id}/medical-reason`);
    expect(res.status).toBe(403);
    expect(((await res.json()) as { code: string }).code).toBe("SEC-01");
    expect(auditEvents().filter((e) => e.action === "claim.medical_reason.read")).toHaveLength(0);
  });

  it("médecin-conseil : chaque lecture crée un événement d'audit distinct", async () => {
    const first = (await (await api("medecin_conseil", `/v1/claims/${REVIEW_CLAIM.id}/medical-reason`)).json()) as {
      audit_event_id: string;
      text: string;
    };
    const second = (await (await api("medecin_conseil", `/v1/claims/${REVIEW_CLAIM.id}/medical-reason`)).json()) as {
      audit_event_id: string;
    };
    expect(first.text).toBe(medicalReasonFor(REVIEW_CLAIM.id));
    expect(first.audit_event_id).not.toBe(second.audit_event_id);
    const reads = auditEvents().filter((e) => e.action === "claim.medical_reason.read");
    expect(reads.map((e) => e.id)).toEqual([first.audit_event_id, second.audit_event_id]);
  });
});

describe("décision du médecin-conseil (R5)", () => {
  const body = JSON.stringify({ decision: "accorder", reason_code: "ACC-01" });

  it("un dossier en revue passe à « accordée » avec une décision humaine tracée", async () => {
    const res = await api("medecin_conseil", `/v1/claims/${REVIEW_CLAIM.id}/decisions`, {
      method: "POST",
      body,
      headers: { "Idempotency-Key": "cle-decision-0001" },
    });
    expect(res.status).toBe(200);
    const detail = (await res.json()) as {
      claim: { status: string };
      decisions: { source: string; outcome: string; reason_code: string }[];
    };
    expect(detail.claim.status).toBe("accordee");
    expect(detail.decisions.at(-1)).toMatchObject({ source: "humain", outcome: "accordee", reason_code: "ACC-01" });
  });

  it("la même clé d'idempotence rejouée ne crée pas de seconde décision", async () => {
    const init = { method: "POST", body, headers: { "Idempotency-Key": "cle-decision-0002" } };
    const a = (await (await api("medecin_conseil", `/v1/claims/${REVIEW_CLAIM.id}/decisions`, init)).json()) as {
      decisions: unknown[];
    };
    const b = (await (await api("medecin_conseil", `/v1/claims/${REVIEW_CLAIM.id}/decisions`, init)).json()) as {
      decisions: unknown[];
    };
    expect(b.decisions).toHaveLength(a.decisions.length);
  });

  it("dossier hors revue : 409 CLM-01 ; gestionnaire : 403", async () => {
    const auto = await api("medecin_conseil", `/v1/claims/${AUTO_CLAIM.id}/decisions`, {
      method: "POST",
      body,
      headers: { "Idempotency-Key": "cle-decision-0003" },
    });
    expect(auto.status).toBe(409);
    expect(((await auto.json()) as { code: string }).code).toBe("CLM-01");
    const gest = await api("gestionnaire", `/v1/claims/${REVIEW_CLAIM.id}/decisions`, {
      method: "POST",
      body,
      headers: { "Idempotency-Key": "cle-decision-0004" },
    });
    expect(gest.status).toBe(403);
  });

  it("une décision en revue ne crée aucun paiement tant que le dossier n'est pas accordé", async () => {
    const entries = (await (await api("gestionnaire", "/v1/ledger/entries")).json()) as {
      items: { source_id: string | null }[];
    };
    expect(entries.items.some((e) => e.source_id === REVIEW_CLAIM.id)).toBe(false);
  });
});
