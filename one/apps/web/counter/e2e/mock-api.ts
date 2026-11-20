import type { Page, Route } from "@playwright/test";
import { contractProblems } from "../src/test/contract-event";
import type {
  ClaimCreated,
  CodeSent,
  CounterDevice,
  CreateClaimRequest,
  CurrentUser,
  Identification,
  MemberStatus,
  OfflinePolicy,
  OfflineSyncRequest,
  OfflineSyncResult,
  Problem,
} from "../src/api/types";

/**
 * Mock de l'API pour les parcours Playwright, typé par le contrat (src/api/schema.d.ts généré
 * depuis specs/openapi.yaml) : une réponse hors contrat ne compile pas. Il est à état (essais de
 * code, file hors ligne), ce que le mode statique de Prism ne permet pas. Données fictives.
 */
export const MEMBER_NUMBER = "MC-00000042";
export const GOOD_CODE = "482913";
const IDENTIFICATION_ID = "0b8f3f5e-4d1c-4a55-9d5a-2f7c1c3e9a01";
const DEVICE_ID = "7d4c2b1a-0f9e-4d8c-b7a6-5e4d3c2b1a09";

export const me: CurrentUser = {
  user: { id: "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d", display_name: "Aya · Comptoir 2", status: "active", roles: [{ role: "clinique", provider_id: "3c2b1a09-8f7e-4d6c-a5b4-c3d2e1f0a9b8" }] },
  organization: { id: "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9", slug: "mulemacare-ci", name: "Clinique Démo du Plateau", country_code: "CI", timezone: "Africa/Abidjan", currency: "XOF", capabilities: ["porteur_de_risque"] },
  roles: [{ role: "clinique", provider_id: "3c2b1a09-8f7e-4d6c-a5b4-c3d2e1f0a9b8" }],
};

export const policy: OfflinePolicy = {
  threshold_xof: 50_000,
  validity_minutes: 120,
  currency: "XOF",
  rules: [
    { code: "R-12", version: 3 },
    { code: "HL-01", version: 1 },
  ],
  tariff: {
    at: "2026-10-01",
    items: [
      { act_code: "CS-GEN", label: "Consultation généraliste", amount_xof: 25_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
      { act_code: "NFS", label: "NFS (numération)", amount_xof: 8_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
      { act_code: "ECG", label: "ECG", amount_xof: 15_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
      { act_code: "ECHO-ABD", label: "Échographie abdominale", amount_xof: 30_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
      { act_code: "RADIO-THX", label: "Radiographie thorax", amount_xof: 18_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
    ],
  },
};

function identification(patch: Partial<Identification> = {}, memberStatus: MemberStatus = "actif"): Identification {
  return {
    id: IDENTIFICATION_ID,
    status: "ouverte",
    qr_verified: true,
    photo_confirmed: null,
    code_verified: false,
    beneficiary: {
      person_id: "5a0e6f1c-2b7d-4e1a-8c33-7d9e0a4b6c12",
      member_number: MEMBER_NUMBER,
      display_name: "Aya Démo",
      photo_url: null,
      plan_code: "ESSENTIEL",
      coverage_rate_bp: 8000,
      member_status: memberStatus,
    },
    ...patch,
  };
}

function problem(p: Omit<Problem, "request_id">): Problem {
  return { ...p, request_id: "req_test" };
}

export interface Recorded {
  method: string;
  path: string;
  headers: Record<string, string>;
  body: unknown;
}

export class MockApi {
  networkDown = false;
  /**
   * Aide de première utilisation (coach marks). Les parcours existants jouent un comptoir déjà pris
   * en main : l'aide est posée « désactivée » avant le premier chargement, sauf `coachMarks = true`.
   */
  coachMarks = false;
  /**
   * Mesure d'usage : les parcours qui ne la testent pas jouent un comptoir qui a déjà refusé (pas
   * de bulle de premier usage) ; « unset » laisse l'appareil vierge. Posé seulement s'il n'existe pas.
   */
  measure: "unset" | "granted" | "refused" = "refused";
  wrongCodes = 0;
  readonly requests: Recorded[] = [];
  registeredPublicKey: string | null = null;
  readonly syncBodies: OfflineSyncRequest[] = [];
  syncOutcome: "confirmee" | "rejetee" = "confirmee";
  /** Droits de l'adhérent fictif : « suspendu » fait refuser la demande par R-01 (états du comptoir). */
  memberStatus: MemberStatus = "actif";
  /** Politique hors ligne indisponible (503) : barème vide sur l'écran des actes. */
  policyDown = false;
  /** Délai de réponse de la politique hors ligne (squelette de chargement). */
  policyDelayMs = 0;

  claimRequests(): Recorded[] {
    return this.requests.filter((r) => r.method === "POST" && r.path === "/v1/claims");
  }

  async install(page: Page): Promise<void> {
    if (!this.coachMarks) {
      await page.addInitScript(() => {
        try {
          if (!window.localStorage.getItem("mulema.comptoir.aide")) window.localStorage.setItem("mulema.comptoir.aide", JSON.stringify({ v: 1, off: true, seen: [] }));
        } catch {
          // Stockage indisponible : rien à poser.
        }
      });
    }
    if (this.measure !== "unset") {
      await page.addInitScript((choice) => {
        try {
          if (!window.localStorage.getItem("mulema.comptoir.mesure.choix")) window.localStorage.setItem("mulema.comptoir.mesure.choix", JSON.stringify({ v: 1, choice }));
        } catch {
          // Stockage indisponible : rien à poser.
        }
      }, this.measure);
    }
    await page.route("**/api/v1/**", (route) => this.handle(route));
  }

  /** Événements de mesure produit reçus (corps tels qu'envoyés). */
  events(): Record<string, unknown>[] {
    return this.requests.filter((r) => r.method === "POST" && r.path === "/v1/telemetry/events").map((r) => r.body as Record<string, unknown>);
  }

  private json(route: Route, status: number, body: unknown, problemJson = false) {
    return route.fulfill({ status, contentType: problemJson ? "application/problem+json" : "application/json", body: JSON.stringify(body) });
  }

  private async handle(route: Route): Promise<void> {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api/, "");
    const method = request.method();
    if (this.networkDown) {
      await route.abort("internetdisconnected");
      return;
    }
    const body: unknown = request.postData() ? JSON.parse(request.postData() ?? "null") : null;
    this.requests.push({ method, path, headers: request.headers(), body });
    if (request.headers()["authorization"] !== "Bearer jeton-de-test-comptoir") {
      await this.json(route, 401, problem({ code: "AUTH-01", message: "Votre session a expiré.", action: "Reconnectez-vous puis recommencez." }), true);
      return;
    }

    // Mesure produit (recordProductEvent) : jugé contre le contrat comme l'API (422 sinon), corps relu par les tests.
    if (method === "POST" && path === "/v1/telemetry/events") {
      if (contractProblems(body).length > 0) return this.json(route, 422, problem({ code: "VAL-01", message: "Cet événement de mesure n'est pas admis.", action: "Corrigez l'événement envoyé par l'écran (liste du contrat d'API)." }), true);
      return route.fulfill({ status: 204 });
    }
    if (method === "GET" && path === "/v1/me") return this.json(route, 200, me);
    if (method === "GET" && path === "/v1/counter/offline-policy") {
      if (this.policyDelayMs > 0) await new Promise((resolve) => setTimeout(resolve, this.policyDelayMs));
      if (this.policyDown) return this.json(route, 503, problem({ code: "SYS-01", message: "Service momentanément indisponible.", action: "Réessayez dans un instant." }), true);
      return this.json(route, 200, policy);
    }
    if (method === "POST" && path === "/v1/counter/devices") {
      this.registeredPublicKey = (body as { public_key: string }).public_key;
      const device: CounterDevice = { id: DEVICE_ID, label: "Comptoir mobile", status: "actif", registered_at: new Date().toISOString() };
      return this.json(route, 201, device);
    }
    if (method === "POST" && path === "/v1/counter/identifications") {
      const number = (body as { member_number?: string }).member_number;
      if (number && number !== MEMBER_NUMBER) {
        return this.json(route, 404, problem({ code: "ID-06", message: "Aucune carte active ne correspond à ce code.", action: "Vérifiez le numéro sur la carte ou demandez une nouvelle carte à la mutuelle." }), true);
      }
      return this.json(route, 201, identification({}, this.memberStatus));
    }
    if (method === "POST" && path.endsWith("/photo-confirmation")) {
      const confirmed = (body as { confirmed: boolean }).confirmed;
      return this.json(route, 200, identification(confirmed ? { photo_confirmed: true } : { photo_confirmed: false, status: "identite_refusee" }, this.memberStatus));
    }
    if (method === "POST" && path.endsWith("/code")) {
      const sent: CodeSent = { sent_at: new Date().toISOString(), expires_at: new Date(Date.now() + 300_000).toISOString() };
      return this.json(route, 202, sent);
    }
    if (method === "POST" && path.endsWith("/code-verification")) {
      const code = (body as { code: string }).code;
      if (code === GOOD_CODE) return this.json(route, 200, identification({ status: "verifiee", photo_confirmed: true, code_verified: true }, this.memberStatus));
      this.wrongCodes += 1;
      if (this.wrongCodes >= 3) {
        return this.json(route, 423, problem({ code: "ID-04", message: "Carte bloquée pendant 15 minutes après 3 codes faux.", action: "Faites patienter l'adhérent ou contactez la mutuelle.", retry_after_seconds: 900 }), true);
      }
      const remaining = 3 - this.wrongCodes;
      return this.json(route, 422, problem({ code: "ID-03", message: `Code incorrect. Il reste ${remaining} essai${remaining > 1 ? "s" : ""}.`, action: "Demandez à l'adhérent de relire le SMS, ou renvoyez le code.", remaining_attempts: remaining }), true);
    }
    if (method === "POST" && path === "/v1/claims") return this.json(route, 201, this.decide(body as CreateClaimRequest));
    if (method === "POST" && path === "/v1/authorizations/offline-sync") {
      const sync = body as OfflineSyncRequest;
      this.syncBodies.push(sync);
      const result: OfflineSyncResult = {
        results: sync.authorizations.map((a, i) =>
          this.syncOutcome === "confirmee"
            ? { offline_ref: a.offline_ref, outcome: "confirmee", reason_code: null, claim_id: `c0000000-0000-4000-8000-00000000000${i}`, authorization_id: `a0000000-0000-4000-8000-00000000000${i}` }
            : { offline_ref: a.offline_ref, outcome: "rejetee", reason_code: "OFF-01", claim_id: null, authorization_id: null },
        ),
      };
      return this.json(route, 200, result);
    }
    await this.json(route, 404, problem({ code: "NOT-01", message: "Introuvable.", action: "Vérifiez la demande." }), true);
  }

  /** Imitation du moteur de règles pour le mock seulement (R-12 : total < 50 000 FCFA). */
  private decide(req: CreateClaimRequest): ClaimCreated {
    const prices = new Map(policy.tariff.items.map((i) => [i.act_code, i.amount_xof]));
    const total = req.items.reduce((sum, item) => sum + (prices.get(item.act_code) ?? 0) * (item.quantity ?? 1), 0);
    const now = new Date();
    if (this.memberStatus === "suspendu") return this.refuse(req, total, now);
    const covered = Math.floor((total * 8000 + 5000) / 10000);
    const auto = total < policy.threshold_xof;
    return {
      claim: {
        id: "e1d2c3b4-a596-4877-8695-a4b3c2d1e0f1",
        claim_number: "PEC-26-09815",
        member_id: "6b5a4938-2716-4a5b-8c7d-6e5f4a3b2c1d",
        member_display_name: "Aya Démo",
        provider_id: "3c2b1a09-8f7e-4d6c-a5b4-c3d2e1f0a9b8",
        provider_name: "Clinique Démo du Plateau",
        service_date: req.service_date,
        requested_at: now.toISOString(),
        status: auto ? "accordee_auto" : "en_revue",
        total_xof: total,
        covered_xof: auto ? covered : 0,
        currency: "XOF",
        fraud_score: 0.06,
        fraud_flagged: false,
        rule: auto ? { code: "R-12", version: 3 } : { code: "R-20", version: 2 },
      },
      decision: {
        outcome: auto ? "accordee_auto" : "en_revue",
        rule: auto ? { code: "R-12", version: 3 } : { code: "R-20", version: 2 },
        reason_code: auto ? "R-12" : "R-20",
        message: auto ? "Accord automatique · toutes les conditions de la règle R-12 sont remplies." : "Le total dépasse 50 000 FCFA : avis du médecin-conseil requis.",
        total_xof: total,
        covered_xof: covered,
        patient_share_xof: total - covered,
        currency: "XOF",
        plan_version_id: "2b3c4d5e-6f70-4812-9a3b-4c5d6e7f8091",
        review_due_at: auto ? null : new Date(now.getTime() + 2 * 3_600_000).toISOString(),
        checks: [],
      },
      authorization: auto
        ? { id: "f0e1d2c3-b4a5-4968-8776-655443322110", authorization_number: "ACC-26-004211", kind: "en_ligne", status: "emise", covered_xof: covered, currency: "XOF", rule: { code: "R-12", version: 3 }, issued_at: now.toISOString(), expires_at: null }
        : null,
    };
  }

  /** Refus R-01 (droits suspendus) : rien n'est pris en charge, le patient paie le total. */
  private refuse(req: CreateClaimRequest, total: number, now: Date): ClaimCreated {
    const rule = { code: "R-01", version: 1 };
    return {
      claim: {
        id: "e1d2c3b4-a596-4877-8695-a4b3c2d1e0f2",
        claim_number: "PEC-26-09816",
        member_id: "6b5a4938-2716-4a5b-8c7d-6e5f4a3b2c1d",
        member_display_name: "Aya Démo",
        provider_id: "3c2b1a09-8f7e-4d6c-a5b4-c3d2e1f0a9b8",
        provider_name: "Clinique Démo du Plateau",
        service_date: req.service_date,
        requested_at: now.toISOString(),
        status: "refusee",
        total_xof: total,
        covered_xof: 0,
        currency: "XOF",
        fraud_score: 0.06,
        fraud_flagged: false,
        rule,
      },
      decision: {
        outcome: "refusee",
        rule,
        reason_code: "R-01",
        message: "Droits suspendus : cotisation impayée. L'adhérent règle sa cotisation, ses droits rouvrent dès le paiement.",
        total_xof: total,
        covered_xof: 0,
        patient_share_xof: total,
        currency: "XOF",
        plan_version_id: "2b3c4d5e-6f70-4812-9a3b-4c5d6e7f8091",
        review_due_at: null,
        checks: [
          { rule, passed: false, message: "Droits suspendus" },
          { rule: { code: "R-04", version: 2 }, passed: true, message: "Prestataire conventionné" },
        ],
      },
      authorization: null,
    };
  }
}
