/**
 * Serveur de mocks de la console, dérivé de specs/openapi.yaml :
 * - seules les opérations du contrat utilisées par la console sont simulées (`handledOperations`) ;
 * - les rôles autorisés sont ceux de `x-roles` ; les erreurs suivent `Problem` et ses codes stables ;
 * - chaque réponse est validée contre le schéma du contrat par tests/unit/contract.test.ts.
 * Pourquoi MSW et pas Prism : voir DEPENDENCIES.md (état, rôles, motif médical audité).
 */
import { http, HttpResponse, type HttpResponseResolver } from "msw";
import type {
  ClaimDecisionRecord,
  ClaimDetail,
  ClaimStatus,
  CountryCode,
  ErrorCode,
  LedgerBalance,
  MedicalReason,
  MemberSummary,
  Role,
  WorkQueue,
} from "@/api/types";
import { API_BASE_URL } from "@/lib/config";
import { DECISION_REASON_PATTERN } from "@/lib/decision-reasons";
import { roleFromDemoToken } from "@/lib/session";
import {
  DEMO_MEMBERS,
  DEMO_PLANS,
  DEMO_USERS,
  LEDGER_ACCOUNTS,
  ORGANIZATION,
  contributionsFor,
  entitlementsFor,
  ledgerLines,
  medicalReasonFor,
} from "./fixtures";
import { EVENT_RULES, buildEvent, type ProductEventName, type ProductEventVariant, type ProductSurface } from "@/lib/telemetry";
import { decisionDraft, joeAnswer, searchHits } from "./joe";
import { productMetrics } from "./metrics";
import { checkBrandingUpdate, checkCreateOrganization, checkDomainVerification } from "./platform";
import { demoState, nextEntryNumber, nextId } from "./store";

type Method = "get" | "post" | "put";
export interface HandledOperation {
  method: Method;
  path: string;
}
export const handledOperations: HandledOperation[] = [];

const EVENT_KEYS = ["name", "surface", "role", "session_id", "duration_ms", "step", "variant"];

const PROBLEM_HEADERS = { "Content-Type": "application/problem+json" };

function problem(status: number, code: ErrorCode, message: string, action: string, extra: Record<string, unknown> = {}) {
  return HttpResponse.json(
    { code, message, action, request_id: `req_demo_${Math.random().toString(36).slice(2, 10)}`, ...extra },
    { status, headers: PROBLEM_HEADERS },
  );
}

const unauthorized = () => problem(401, "AUTH-01", "Votre session a expiré.", "Reconnectez-vous puis recommencez.");
const forbidden = () =>
  problem(403, "AUTH-02", "Votre rôle ne permet pas cette action.", "Demandez l'accès à l'administrateur de la mutuelle.");
const notFound = () =>
  problem(404, "NOT-01", "Élément introuvable.", "Vérifiez le lien ou revenez à la liste.");

type Resolver = (args: { request: Request; params: Record<string, string>; role: Role; userId: string }) => Response | Promise<Response>;

/** Déclare une opération du contrat, avec ses rôles autorisés (x-roles). */
function route(method: Method, path: string, roles: Role[], resolver: Resolver, onForbidden = forbidden) {
  handledOperations.push({ method, path });
  const mswPath = `${API_BASE_URL}${path.replace(/\{(\w+)\}/g, ":$1")}`;
  const handler: HttpResponseResolver = async ({ request, params }) => {
    const auth = request.headers.get("authorization") ?? "";
    const role = roleFromDemoToken(auth.replace(/^Bearer\s+/i, ""));
    if (!role) return unauthorized();
    if (!roles.includes(role)) return onForbidden();
    return resolver({
      request,
      params: params as Record<string, string>,
      role,
      userId: DEMO_USERS[role].user.id,
    });
  };
  return method === "get" ? http.get(mswPath, handler) : method === "put" ? http.put(mswPath, handler) : http.post(mswPath, handler);
}

function page<T>(items: T[], url: URL): { items: T[]; page: { next_cursor: string | null } } {
  const limit = Math.min(200, Math.max(1, Number(url.searchParams.get("limit") ?? 50)));
  const offset = Number(url.searchParams.get("cursor") ?? 0) || 0;
  const slice = items.slice(offset, offset + limit);
  const next = offset + limit < items.length ? String(offset + limit) : null;
  return { items: slice, page: { next_cursor: next } };
}

const today = (): string => new Date().toISOString().slice(0, 10);
const findClaim = (id: string): ClaimDetail | undefined => demoState().claims.find((c) => c.claim.id === id);

const ALL: Role[] = ["gestionnaire", "medecin_conseil", "clinique", "employeur", "admin", "assureur", "admin_plateforme"];
const GEST: Role[] = ["gestionnaire", "admin"];

export const handlers = [
  // ------------------------------------------------------------------ L1
  route("get", "/v1/me", ALL, ({ role }) => HttpResponse.json(DEMO_USERS[role as keyof typeof DEMO_USERS])),
  route("get", "/v1/organization", ALL, ({ role }) => HttpResponse.json(DEMO_USERS[role as keyof typeof DEMO_USERS].organization ?? ORGANIZATION)),

  // ------------------------------------------------------------------ L5 prises en charge
  route("get", "/v1/work-queue", ["gestionnaire", "medecin_conseil", "admin"], () => {
    const claims = demoState().claims.map((d) => d.claim);
    const unpaid = DEMO_MEMBERS.filter((m) =>
      contributionsFor(m).some((c) => c.status === "en_retard" && Date.parse(c.due_on) < Date.now() - 30 * 86_400_000),
    );
    const body: WorkQueue = {
      claims_in_review: claims.filter((c) => c.status === "en_revue").length,
      fraud_alerts: claims.filter((c) => c.fraud_flagged).length,
      members_unpaid_over_30_days: unpaid.length,
      auto_approved_today: claims.filter((c) => c.status === "accordee_auto" && c.requested_at.slice(0, 10) === today()).length,
    };
    return HttpResponse.json(body);
  }),

  route("get", "/v1/claims", ["gestionnaire", "medecin_conseil", "clinique", "admin"], ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get("status") as ClaimStatus | null;
    const fraud = url.searchParams.get("fraud_flagged");
    const memberId = url.searchParams.get("member_id");
    const from = url.searchParams.get("from");
    const to = url.searchParams.get("to");
    const items = demoState()
      .claims.map((d) => d.claim)
      .filter((c) => !status || c.status === status)
      .filter((c) => fraud === null || c.fraud_flagged === (fraud === "true"))
      .filter((c) => !memberId || c.member_id === memberId)
      .filter((c) => !from || c.service_date >= from)
      .filter((c) => !to || c.service_date <= to)
      .sort((a, b) => b.requested_at.localeCompare(a.requested_at));
    return HttpResponse.json(page(items, url));
  }),

  route("get", "/v1/claims/{claim_id}", ["gestionnaire", "medecin_conseil", "clinique", "admin"], ({ params }) => {
    const detail = findClaim(params["claim_id"]!);
    return detail ? HttpResponse.json(detail) : notFound();
  }),

  route(
    "get",
    "/v1/claims/{claim_id}/medical-reason",
    ["medecin_conseil"],
    ({ params, role, userId }) => {
      const detail = findClaim(params["claim_id"]!);
      if (!detail) return notFound();
      const readAt = new Date().toISOString();
      const auditId = nextId();
      demoState().audit.push({
        id: auditId,
        occurred_at: readAt,
        actor_user_id: userId,
        actor_role: role,
        action: "claim.medical_reason.read",
        target_type: "claim",
        target_id: detail.claim.id,
        request_id: null,
      });
      const body: MedicalReason = {
        claim_id: detail.claim.id,
        text: medicalReasonFor(detail.claim.id),
        source: "healthos",
        read_at: readAt,
        audit_event_id: auditId,
      };
      return HttpResponse.json(body, { headers: { "Cache-Control": "no-store" } });
    },
    () =>
      problem(
        403,
        "SEC-01",
        "Le motif médical est réservé au médecin-conseil.",
        "Demandez l'avis du médecin-conseil depuis le dossier.",
      ),
  ),

  route("post", "/v1/claims/{claim_id}/decisions", ["medecin_conseil"], async ({ request, params, userId }) => {
    const key = request.headers.get("idempotency-key") ?? "";
    const raw = await request.text();
    if (key.length < 8 || key.length > 200) {
      return problem(422, "VAL-01", "La clé d'idempotence est absente ou invalide.", "Rechargez la page puis recommencez.", {
        errors: [{ field: "Idempotency-Key", message: "8 à 200 caractères." }],
      });
    }
    const replay = demoState().idempotency.get(key);
    if (replay) {
      if (replay.fingerprint !== raw) {
        return problem(409, "IDEM-01", "Cette demande a déjà été envoyée avec un autre contenu.", "Rechargez le dossier avant de décider.");
      }
      return HttpResponse.json(replay.body, { status: replay.status });
    }

    let body: { decision?: unknown; reason_code?: unknown };
    try {
      body = JSON.parse(raw) as typeof body;
    } catch {
      body = {};
    }
    const decisions = ["accorder", "refuser", "demander_pieces"] as const;
    const decision = decisions.find((d) => d === body.decision);
    const reason = typeof body.reason_code === "string" ? body.reason_code : "";
    if (!decision || !DECISION_REASON_PATTERN.test(reason)) {
      return problem(422, "VAL-01", "La décision est incomplète.", "Choisissez une décision et un motif codé.", {
        errors: [
          ...(!decision ? [{ field: "decision", message: "Valeur attendue : accorder, refuser ou demander_pieces." }] : []),
          ...(!DECISION_REASON_PATTERN.test(reason) ? [{ field: "reason_code", message: "Motif codé attendu (ex. ACC-01)." }] : []),
        ],
      });
    }

    const detail = findClaim(params["claim_id"]!);
    if (!detail) return notFound();
    if (detail.claim.status !== "en_revue") {
      return problem(409, "CLM-01", "Ce dossier n'est plus en revue.", "Rechargez le dossier pour voir sa dernière décision.");
    }

    const outcome: ClaimDecisionRecord["outcome"] =
      decision === "accorder" ? "accordee" : decision === "refuser" ? "refusee" : "pieces_demandees";
    const now = new Date().toISOString();
    detail.decisions.push({
      sequence: detail.decisions.length + 1,
      outcome,
      source: "humain",
      rule: null,
      reason_code: reason,
      decided_by: userId,
      decided_at: now,
    });
    detail.claim.status = outcome;
    detail.review_due_at = null;

    if (decision === "refuser") {
      detail.claim.covered_xof = 0;
      detail.items = detail.items.map((it) => ({ ...it, covered_xof: 0 }));
      detail.patient_share_xof = detail.claim.total_xof;
    }
    if (decision === "accorder") {
      const covered = detail.claim.covered_xof;
      const rule = detail.claim.rule ?? { code: "R-20", version: 2 };
      detail.authorization = {
        id: nextId(),
        authorization_number: `ACC-${detail.claim.claim_number.slice(4)}`,
        kind: "en_ligne",
        status: "emise",
        covered_xof: covered,
        currency: "XOF",
        rule,
        issued_at: now,
        expires_at: null,
      };
      // Effet du consommateur claim.decided (L3) : charge de prestation / dette prestataire.
      demoState().ledger.push({
        id: nextId(),
        entry_number: nextEntryNumber(),
        accounting_date: now.slice(0, 10),
        posted_at: now,
        label: `${detail.claim.claim_number} · accord après revue`,
        source_type: "prise_en_charge",
        source_id: detail.claim.id,
        reverses_entry_id: null,
        reversed_by_entry_id: null,
        currency: "XOF",
        lines: ledgerLines([
          ["6011", covered, 0, { member: detail.claim.member_id }],
          ["4011", 0, covered, { provider: detail.claim.provider_id }],
        ]),
      });
    }

    const reply = structuredClone(detail);
    demoState().idempotency.set(key, { fingerprint: raw, status: 200, body: reply });
    return HttpResponse.json(reply);
  }),

  // ------------------------------------------------------------------ L4 adhérents
  route("get", "/v1/members", GEST, ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const q = (url.searchParams.get("q") ?? "").trim().toLocaleLowerCase("fr");
    if (q && q.length < 2) {
      return problem(422, "VAL-01", "La recherche doit contenir au moins 2 caractères.", "Précisez votre recherche.");
    }
    const items: MemberSummary[] = DEMO_MEMBERS.filter((m) => !status || m.status === status)
      .filter((m) => {
        if (!q) return true;
        const hay = `${m.holder.given_name} ${m.holder.family_name} ${m.member_number}`.toLocaleLowerCase("fr");
        return hay.includes(q);
      })
      .map((m) => ({
        id: m.id,
        member_number: m.member_number,
        given_name: m.holder.given_name,
        family_name: m.holder.family_name,
        plan_code: m.plan_code,
        status: m.status,
      }));
    return HttpResponse.json(page(items, url));
  }),

  route("get", "/v1/members/{member_id}", GEST, ({ params }) => {
    const member = DEMO_MEMBERS.find((m) => m.id === params["member_id"]);
    return member ? HttpResponse.json(member) : notFound();
  }),

  route("get", "/v1/members/{member_id}/entitlements", ["gestionnaire", "medecin_conseil", "admin"], ({ params, request }) => {
    const member = DEMO_MEMBERS.find((m) => m.id === params["member_id"]);
    if (!member) return notFound();
    const at = new URL(request.url).searchParams.get("at") ?? today();
    return HttpResponse.json(entitlementsFor(member, at));
  }),

  route("get", "/v1/members/{member_id}/contributions", GEST, ({ params }) => {
    const member = DEMO_MEMBERS.find((m) => m.id === params["member_id"]);
    return member ? HttpResponse.json({ items: contributionsFor(member) }) : notFound();
  }),

  // ------------------------------------------------------------------ L3 grand livre
  route("get", "/v1/ledger/accounts", GEST, () => HttpResponse.json({ items: LEDGER_ACCOUNTS })),

  route("get", "/v1/ledger/entries", GEST, ({ request }) => {
    const url = new URL(request.url);
    const account = url.searchParams.get("account_code");
    const items = [...demoState().ledger]
      .filter((e) => !account || e.lines.some((l) => l.account_code === account))
      .sort((a, b) => b.posted_at.localeCompare(a.posted_at));
    return HttpResponse.json(page(items, url));
  }),

  route("get", "/v1/ledger/entries/{entry_id}", GEST, ({ params }) => {
    const entry = demoState().ledger.find((e) => e.id === params["entry_id"]);
    return entry ? HttpResponse.json(entry) : notFound();
  }),

  route("get", "/v1/ledger/balance", GEST, ({ request }) => {
    const at = new URL(request.url).searchParams.get("at") ?? today();
    const rows = LEDGER_ACCOUNTS.map((a) => {
      const lines = demoState()
        .ledger.filter((e) => e.accounting_date <= at)
        .flatMap((e) => e.lines)
        .filter((l) => l.account_code === a.code);
      return {
        account_code: a.code,
        account_label: a.label,
        debit_xof: lines.reduce((s, l) => s + l.debit_xof, 0),
        credit_xof: lines.reduce((s, l) => s + l.credit_xof, 0),
      };
    });
    const body: LedgerBalance = {
      at,
      currency: "XOF",
      rows,
      total_debit_xof: rows.reduce((s, r) => s + r.debit_xof, 0),
      total_credit_xof: rows.reduce((s, r) => s + r.credit_xof, 0),
    };
    return HttpResponse.json(body);
  }),

  // ------------------------------------------------------------------ P2 mesure produit
  route("post", "/v1/telemetry/events", ["gestionnaire", "medecin_conseil", "clinique", "employeur", "admin", "adherent", "assureur", "admin_plateforme"], async ({ request, role }) => {
    const invalid = () => problem(422, "VAL-01", "Cet événement de mesure n'est pas admis.", "Corrigez l'événement envoyé par l'écran (liste du contrat d'API).");
    const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
    if (!body || typeof body !== "object") return invalid();
    if (body.role !== role) return problem(403, "AUTH-02", "Ce rôle n'est pas celui de votre session.", "Rechargez la page puis recommencez.");
    const name = typeof body.name === "string" && Object.hasOwn(EVENT_RULES, body.name) ? (body.name as ProductEventName) : null;
    const unknownKeys = Object.keys(body).filter((k) => !EVENT_KEYS.includes(k));
    const sessionId = typeof body.session_id === "string" ? body.session_id : "";
    if (!name || unknownKeys.length > 0 || !/^[0-9a-f]{32}$/.test(sessionId)) return invalid();
    const props = {
      ...(body.variant !== undefined ? { variant: body.variant as ProductEventVariant } : {}),
      ...(typeof body.step === "number" ? { step: body.step } : {}),
      ...(typeof body.duration_ms === "number" ? { duration_ms: body.duration_ms } : {}),
    };
    const event = buildEvent(name, props, { surface: body.surface as ProductSurface, role, sessionId });
    // Le corps reçu doit être exactement celui que les règles admettent (pas de champ arrondi ou retiré).
    if (!event || JSON.stringify(Object.entries(event).sort()) !== JSON.stringify(Object.entries(body).sort())) return invalid();
    demoState().productEvents.push(event);
    return new HttpResponse(null, { status: 204 });
  }),

  route("get", "/v1/metrics/product", GEST, ({ request }) => {
    const url = new URL(request.url);
    return HttpResponse.json(productMetrics(url.searchParams.get("from"), url.searchParams.get("to")));
  }),

  // ------------------------------------------------------------------ L8 JOE et recherche ⌘K
  route("get", "/v1/search", ["gestionnaire", "medecin_conseil", "clinique", "admin"], ({ request, role }) => {
    const q = new URL(request.url).searchParams.get("q") ?? "";
    if (q.trim().length < 2 || q.length > 200) {
      return problem(422, "VAL-01", "La recherche doit contenir au moins 2 caractères.", "Précisez votre recherche.", {
        errors: [{ field: "q", message: "2 à 200 caractères." }],
      });
    }
    return HttpResponse.json({ items: searchHits(q, role) });
  }),

  route("post", "/v1/joe/questions", ["gestionnaire", "medecin_conseil", "admin"], async ({ request, userId }) => {
    const body = (await request.json().catch(() => ({}))) as { question?: unknown; claim_id?: unknown; member_id?: unknown };
    const question = typeof body.question === "string" ? body.question : "";
    if (question.trim().length < 2 || question.length > 1000) {
      return problem(422, "VAL-01", "La question est vide ou trop longue.", "Posez une question de 2 à 1 000 caractères.", {
        errors: [{ field: "question", message: "2 à 1 000 caractères." }],
      });
    }
    return HttpResponse.json(
      joeAnswer(
        {
          question,
          ...(typeof body.claim_id === "string" ? { claim_id: body.claim_id } : {}),
          ...(typeof body.member_id === "string" ? { member_id: body.member_id } : {}),
        },
        userId,
      ),
    );
  }),

  route("post", "/v1/joe/decision-drafts", ["medecin_conseil"], async ({ request, userId }) => {
    const body = (await request.json().catch(() => ({}))) as { claim_id?: unknown };
    const draft = typeof body.claim_id === "string" ? decisionDraft(body.claim_id, userId) : null;
    return draft ? HttpResponse.json(draft) : notFound();
  }),

  route("get", "/v1/ai-actions", ["admin"], ({ request }) => {
    const url = new URL(request.url);
    const items = [...demoState().aiActions].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
    return HttpResponse.json(page(items, url));
  }),

  // ------------------------------------------------------------------ P3 marque blanche (admin de l'organisation)
  route("get", "/v1/organization/branding", ["admin"], () => HttpResponse.json(demoState().branding)),
  route("put", "/v1/organization/branding", ["admin"], async ({ request }) => {
    const body: unknown = await request.json().catch(() => null);
    const result = checkBrandingUpdate(body, new Date().toISOString(), demoState().branding);
    if ("code" in result) return problem(result.status, result.code, result.message, result.action, result.errors ? { errors: result.errors } : {});
    demoState().branding = result;
    return HttpResponse.json(result);
  }),

  route("post", "/v1/organization/branding/domain-verification", ["admin"], () => {
    const result = checkDomainVerification(demoState().branding);
    if ("code" in result) return problem(result.status, result.code, result.message, result.action, result.errors ? { errors: result.errors } : {});
    demoState().branding = result;
    return HttpResponse.json(result);
  }),

  // ------------------------------------------------------------------ P3 plateforme (admin_plateforme)
  route("get", "/v1/platform/configuration-templates", ["admin_plateforme"], () => HttpResponse.json({ items: demoState().templates })),
  route("post", "/v1/platform/configuration-templates", ["admin_plateforme"], async ({ request }) => {
    const body = (await request.json().catch(() => null)) as { code?: unknown; country_code?: unknown; label?: unknown } | null;
    const code = typeof body?.code === "string" && /^[a-z0-9][a-z0-9-]{1,39}$/.test(body.code) ? body.code : null;
    const country: CountryCode | null = body?.country_code === "CI" || body?.country_code === "SN" ? body.country_code : null;
    const label = typeof body?.label === "string" && body.label.length >= 1 && body.label.length <= 120 ? body.label : null;
    if (!code || !country || !label) {
      return problem(422, "VAL-01", "Certaines informations sont invalides.", "Corrigez les champs signalés puis recommencez.", {
        errors: [...(code ? [] : [{ field: "code", message: "2 à 40 caractères : minuscules, chiffres, tirets." }]), ...(country ? [] : [{ field: "country_code", message: "CI ou SN." }]), ...(label ? [] : [{ field: "label", message: "1 à 120 caractères." }])],
      });
    }
    const templates = demoState().templates;
    const version = Math.max(0, ...templates.filter((t) => t.code === code).map((t) => t.version)) + 1;
    const latest = templates.filter((t) => t.country_code === country).sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
    const created = { id: nextId(), code, version, country_code: country, label, created_at: new Date().toISOString(), contents: latest?.contents ?? { ledger_accounts: 0, rules: 0, plans: 0, coverages: 0, acts: 0, tariff_items: 0 } };
    templates.push(created);
    return HttpResponse.json(created, { status: 201 });
  }),
  route("post", "/v1/platform/organizations", ["admin_plateforme"], async ({ request }) => {
    const body: unknown = await request.json().catch(() => null);
    const state = demoState();
    const result = checkCreateOrganization(body, { takenSlugs: state.takenSlugs, templates: state.templates, newId: nextId });
    if ("code" in result) return problem(result.status, result.code, result.message, result.action, result.errors ? { errors: result.errors } : {});
    state.takenSlugs.push(result.organization.slug);
    return HttpResponse.json(result, { status: 201 });
  }),

  // ------------------------------------------------------------------ L2 produits
  route("get", "/v1/plans", GEST, () => HttpResponse.json({ items: DEMO_PLANS })),
  route("get", "/v1/plans/{plan_id}", GEST, ({ params }) => {
    const plan = DEMO_PLANS.find((p) => p.id === params["plan_id"]);
    return plan ? HttpResponse.json(plan) : notFound();
  }),
  route("get", "/v1/plan-versions/{plan_version_id}", GEST, ({ params }) => {
    const version = DEMO_PLANS.flatMap((p) => p.versions).find((v) => v.id === params["plan_version_id"]);
    return version ? HttpResponse.json(version) : notFound();
  }),
];
