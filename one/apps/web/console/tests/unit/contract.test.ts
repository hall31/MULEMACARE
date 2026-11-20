/**
 * Le serveur de mocks est « issu de l'OpenAPI » : chaque route simulée existe dans
 * specs/openapi.yaml, et chaque réponse simulée est validée contre le schéma du contrat.
 * Si un mock dérive du contrat, ce test échoue.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import { API_BASE_URL } from "../../src/lib/config";
import { demoToken, type DemoRole } from "../../src/lib/session";
import { handledOperations } from "../../src/mocks/handlers";
import { DEMO_MEMBERS, DEMO_CLAIMS, PLAN_FAMILLE_OR, REVIEW_CLAIM, AUTO_CLAIM } from "../../src/mocks/fixtures";
import { TAKEN_DOMAIN } from "../../src/mocks/platform";
import { BRANDING_FIXTURES } from "@shared/brand";

const here = path.dirname(fileURLToPath(import.meta.url));
const specPath = path.resolve(here, "../../../../../specs/openapi.yaml");

type Json = Record<string, unknown>;
const spec = parse(readFileSync(specPath, "utf8")) as Json & { paths: Record<string, Record<string, Json>> };

const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
ajv.addFormat("int64", true);
ajv.addSchema(spec, "openapi.json");

function resolveRef(node: Json): Json {
  const ref = node["$ref"];
  if (typeof ref !== "string") return node;
  let cur: unknown = spec;
  for (const part of ref.replace(/^#\//, "").split("/")) cur = (cur as Json)[part];
  return cur as Json;
}

function responseSchemaRef(method: string, template: string, status: number): { ref: string; mediaType: string } {
  const op = spec.paths[template]?.[method];
  if (!op) throw new Error(`Opération absente du contrat : ${method.toUpperCase()} ${template}`);
  const responses = op["responses"] as Record<string, Json>;
  const raw = responses[String(status)];
  if (!raw) throw new Error(`Statut ${status} non prévu par le contrat pour ${method.toUpperCase()} ${template}`);
  const response = resolveRef(raw);
  const content = response["content"] as Record<string, Json>;
  const mediaType = Object.keys(content)[0]!;
  const media = mediaType.replace("/", "~1");
  const encodedPath = template.replaceAll("/", "~1").replaceAll("{", "%7B").replaceAll("}", "%7D");
  const pointer =
    typeof raw["$ref"] === "string"
      ? `${raw["$ref"]}/content/${media}/schema`
      : `#/paths/${encodedPath}/${method}/responses/${status}/content/${media}/schema`;
  return { ref: `openapi.json${pointer}`, mediaType };
}

interface Case {
  role: DemoRole;
  method: "get" | "post" | "put";
  template: string;
  url: string;
  status: number;
  body?: unknown;
  headers?: Record<string, string>;
}

const member = DEMO_MEMBERS[0]!;
const plan = PLAN_FAMILLE_OR;
const version = plan.versions[0]!;

const cases: Case[] = [
  { role: "gestionnaire", method: "get", template: "/v1/me", url: "/v1/me", status: 200 },
  { role: "medecin_conseil", method: "get", template: "/v1/me", url: "/v1/me", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/work-queue", url: "/v1/work-queue", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/claims", url: "/v1/claims", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/claims", url: "/v1/claims?status=en_revue", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/claims", url: "/v1/claims?fraud_flagged=true", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/claims/{claim_id}", url: `/v1/claims/${REVIEW_CLAIM.id}`, status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/claims/{claim_id}", url: `/v1/claims/${AUTO_CLAIM.id}`, status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/claims/{claim_id}", url: "/v1/claims/00000000-0000-4000-8000-00000000dead", status: 404 },
  { role: "gestionnaire", method: "get", template: "/v1/claims/{claim_id}/medical-reason", url: `/v1/claims/${REVIEW_CLAIM.id}/medical-reason`, status: 403 },
  { role: "medecin_conseil", method: "get", template: "/v1/claims/{claim_id}/medical-reason", url: `/v1/claims/${REVIEW_CLAIM.id}/medical-reason`, status: 200 },
  {
    role: "gestionnaire", method: "post", template: "/v1/claims/{claim_id}/decisions", url: `/v1/claims/${REVIEW_CLAIM.id}/decisions`,
    status: 403, body: { decision: "accorder", reason_code: "ACC-01" }, headers: { "Idempotency-Key": "test-cle-0001" },
  },
  {
    role: "medecin_conseil", method: "post", template: "/v1/claims/{claim_id}/decisions", url: `/v1/claims/${AUTO_CLAIM.id}/decisions`,
    status: 409, body: { decision: "accorder", reason_code: "ACC-01" }, headers: { "Idempotency-Key": "test-cle-0002" },
  },
  {
    role: "medecin_conseil", method: "post", template: "/v1/claims/{claim_id}/decisions", url: `/v1/claims/${REVIEW_CLAIM.id}/decisions`,
    status: 422, body: { decision: "accorder", reason_code: "texte libre" }, headers: { "Idempotency-Key": "test-cle-0003" },
  },
  {
    role: "medecin_conseil", method: "post", template: "/v1/claims/{claim_id}/decisions", url: `/v1/claims/${REVIEW_CLAIM.id}/decisions`,
    status: 200, body: { decision: "accorder", reason_code: "ACC-01" }, headers: { "Idempotency-Key": "test-cle-0004" },
  },
  { role: "gestionnaire", method: "get", template: "/v1/members", url: "/v1/members", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/members", url: "/v1/members?q=ko&status=actif", status: 200 },
  { role: "medecin_conseil", method: "get", template: "/v1/members", url: "/v1/members", status: 403 },
  { role: "gestionnaire", method: "get", template: "/v1/members/{member_id}", url: `/v1/members/${member.id}`, status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/members/{member_id}/entitlements", url: `/v1/members/${member.id}/entitlements`, status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/members/{member_id}/contributions", url: `/v1/members/${member.id}/contributions`, status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/claims", url: `/v1/claims?member_id=${member.id}`, status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/ledger/accounts", url: "/v1/ledger/accounts", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/ledger/entries", url: "/v1/ledger/entries", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/ledger/entries", url: "/v1/ledger/entries?account_code=6011", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/ledger/balance", url: "/v1/ledger/balance", status: 200 },
  { role: "medecin_conseil", method: "get", template: "/v1/ledger/entries", url: "/v1/ledger/entries", status: 403 },
  { role: "gestionnaire", method: "get", template: "/v1/plans", url: "/v1/plans", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/plans/{plan_id}", url: `/v1/plans/${plan.id}`, status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/plan-versions/{plan_version_id}", url: `/v1/plan-versions/${version.id}`, status: 200 },
  // L8 : recherche ⌘K et JOE (lecture et préparation seulement).
  { role: "gestionnaire", method: "get", template: "/v1/search", url: "/v1/search?q=ko", status: 200 },
  { role: "medecin_conseil", method: "get", template: "/v1/search", url: "/v1/search?q=PEC-26", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/search", url: "/v1/search?q=k", status: 422 },
  { role: "gestionnaire", method: "post", template: "/v1/joe/questions", url: "/v1/joe/questions", status: 200, body: { question: "Combien de dossiers sont en revue ?" } },
  { role: "medecin_conseil", method: "post", template: "/v1/joe/questions", url: "/v1/joe/questions", status: 200, body: { question: "Où en est ce dossier ?", claim_id: REVIEW_CLAIM.id } },
  { role: "medecin_conseil", method: "post", template: "/v1/joe/questions", url: "/v1/joe/questions", status: 200, body: { question: "Quel est le diagnostic ?" } },
  { role: "gestionnaire", method: "post", template: "/v1/joe/questions", url: "/v1/joe/questions", status: 422, body: { question: "x" } },
  { role: "medecin_conseil", method: "post", template: "/v1/joe/decision-drafts", url: "/v1/joe/decision-drafts", status: 200, body: { claim_id: REVIEW_CLAIM.id } },
  { role: "gestionnaire", method: "post", template: "/v1/joe/decision-drafts", url: "/v1/joe/decision-drafts", status: 403, body: { claim_id: REVIEW_CLAIM.id } },
  { role: "medecin_conseil", method: "post", template: "/v1/joe/decision-drafts", url: "/v1/joe/decision-drafts", status: 404, body: { claim_id: "00000000-0000-4000-8000-00000000dead" } },
  { role: "gestionnaire", method: "get", template: "/v1/ai-actions", url: "/v1/ai-actions", status: 403 },
  // P2 : mesure produit.
  { role: "gestionnaire", method: "get", template: "/v1/metrics/product", url: "/v1/metrics/product", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/metrics/product", url: "/v1/metrics/product?from=2026-01-01&to=2026-12-31", status: 200 },
  { role: "medecin_conseil", method: "get", template: "/v1/metrics/product", url: "/v1/metrics/product", status: 403 },
  {
    role: "gestionnaire", method: "post", template: "/v1/telemetry/events", url: "/v1/telemetry/events", status: 422,
    body: { name: "palette_opened", surface: "console", role: "gestionnaire", session_id: "0123456789abcdef0123456789abcdef", variant: "clavier", question: "texte libre" },
  },
  {
    role: "gestionnaire", method: "post", template: "/v1/telemetry/events", url: "/v1/telemetry/events", status: 403,
    body: { name: "palette_opened", surface: "console", role: "admin", session_id: "0123456789abcdef0123456789abcdef", variant: "clavier" },
  },
  // P3 : marque blanche (admin de l'organisation) et plateforme (admin_plateforme).
  { role: "admin", method: "get", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 200 },
  { role: "gestionnaire", method: "get", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 403 },
  { role: "admin", method: "put", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 200, body: brandingBody() },
  { role: "admin", method: "put", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 422, body: brandingBody({ theme: { light: { accent: "#ffd400" } } }) },
  { role: "admin", method: "put", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 422, body: brandingBody({ theme: { light: { bg: "#000000" } } }) },
  { role: "admin", method: "put", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 422, body: brandingBody({ logo: { kind: "url", src: "javascript:alert(1)" } }) },
  { role: "admin", method: "put", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 409, body: brandingBody({ custom_domain: TAKEN_DOMAIN }) },
  { role: "admin", method: "put", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 422, body: brandingBody({ custom_domain: "payer.mulemacare.invalid" }) },
  { role: "admin", method: "post", template: "/v1/organization/branding/domain-verification", url: "/v1/organization/branding/domain-verification", status: 422 },
  { role: "gestionnaire", method: "post", template: "/v1/organization/branding/domain-verification", url: "/v1/organization/branding/domain-verification", status: 403 },
  { role: "admin_plateforme", method: "get", template: "/v1/me", url: "/v1/me", status: 200 },
  { role: "admin_plateforme", method: "get", template: "/v1/platform/configuration-templates", url: "/v1/platform/configuration-templates", status: 200 },
  { role: "admin", method: "get", template: "/v1/platform/configuration-templates", url: "/v1/platform/configuration-templates", status: 403 },
  { role: "admin_plateforme", method: "post", template: "/v1/platform/configuration-templates", url: "/v1/platform/configuration-templates", status: 201, body: { code: "mutuelle-ci", country_code: "CI", label: "Mutuelle santé Côte d'Ivoire (référence)" } },
  { role: "admin_plateforme", method: "post", template: "/v1/platform/organizations", url: "/v1/platform/organizations", status: 201, body: organizationBody() },
  { role: "admin_plateforme", method: "post", template: "/v1/platform/organizations", url: "/v1/platform/organizations", status: 409, body: organizationBody({ slug: "lagune-sante" }) },
  { role: "admin_plateforme", method: "post", template: "/v1/platform/organizations", url: "/v1/platform/organizations", status: 422, body: organizationBody({ country_code: "SN" }) },
  { role: "gestionnaire", method: "post", template: "/v1/platform/organizations", url: "/v1/platform/organizations", status: 403, body: organizationBody() },
];

function brandingBody(change: Record<string, unknown> = {}) {
  return { display_name: "Mutuelle Lagune Santé", logo: BRANDING_FIXTURES["lagune-sante"]!.logo, theme: BRANDING_FIXTURES["lagune-sante"]!.theme, custom_domain: null, legal_notice: null, privacy_notice: null, ...change };
}

function organizationBody(change: Record<string, unknown> = {}) {
  return {
    slug: "mutuelle-bouake",
    name: "Mutuelle de Bouaké",
    country_code: "CI",
    capabilities: ["porteur_de_risque", "gestionnaire"],
    regulator: null,
    first_manager: { idp_subject: "idp|bouake-001", display_name: "Adjoua Kouamé", email: "gestion@bouake.invalid" },
    template: { code: "mutuelle-ci" },
    ...change,
  };
}

async function call(c: Case): Promise<Response> {
  return fetch(`${API_BASE_URL}${c.url}`, {
    method: c.method.toUpperCase(),
    headers: {
      Authorization: `Bearer ${demoToken(c.role)}`,
      ...(c.body ? { "Content-Type": "application/json" } : {}),
      ...c.headers,
    },
    body: c.body ? JSON.stringify(c.body) : undefined,
  });
}

describe("serveur de mocks conforme à specs/openapi.yaml", () => {
  it("ne simule que des opérations qui existent dans le contrat", () => {
    const missing = handledOperations.filter((op) => !spec.paths[op.path]?.[op.method]);
    expect(missing).toEqual([]);
  });

  it.each(cases.map((c) => [`${c.role} ${c.method.toUpperCase()} ${c.url} → ${c.status}`, c] as const))(
    "%s",
    async (_label, c) => {
      const res = await call(c);
      expect(res.status).toBe(c.status);
      const { ref, mediaType } = responseSchemaRef(c.method, c.template, c.status);
      expect(res.headers.get("content-type") ?? "").toContain(mediaType);
      const validate = ajv.compile({ $ref: ref });
      const body: unknown = await res.json();
      const ok = validate(body);
      expect(validate.errors ?? [], JSON.stringify(body).slice(0, 400)).toEqual([]);
      expect(ok).toBe(true);
    },
  );

  it("événement de mesure admis : 204 sans corps (recordProductEvent)", async () => {
    const res = await call({
      role: "medecin_conseil", method: "post", template: "/v1/telemetry/events", url: "/v1/telemetry/events", status: 204,
      body: { name: "joe_question_asked", surface: "console", role: "medecin_conseil", session_id: "0123456789abcdef0123456789abcdef", variant: "saisie" },
    });
    expect(res.status).toBe(204);
    expect(spec.paths["/v1/telemetry/events"]?.post?.["responses"]).toHaveProperty("204");
    expect(await res.text()).toBe("");
  });

  it.each([
    ["identifiant de session hors format (CR-P2-02)", { session_id: "AbCdEfGhIjKlMnOpQrStUv" }],
    ["identifiant de session en majuscules", { session_id: "0123456789ABCDEF0123456789ABCDEF" }],
    ["durée sur un événement qui n'en admet pas", { duration_ms: 812 }],
  ])("événement de mesure refusé en 422 : %s", async (_label, change) => {
    const res = await call({
      role: "medecin_conseil", method: "post", template: "/v1/telemetry/events", url: "/v1/telemetry/events", status: 422,
      body: { name: "joe_question_asked", surface: "console", role: "medecin_conseil", session_id: "0123456789abcdef0123456789abcdef", variant: "saisie", ...change },
    });
    expect(res.status).toBe(422);
  });

  it.each([
    ["contraste insuffisant", { theme: { light: { accent: "#ffd400" } } }, 422, "BRD-01", "theme.light.accent"],
    ["accent égal à un statut", { theme: { light: { accent: "#b91c1c" } } }, 422, "BRD-01", "theme.light.accent"],
    ["jeton hors liste fermée", { theme: { light: { bg: "#000000" } } }, 422, "BRD-02", "theme.light.bg"],
    ["plein soleil surchargé", { theme: { sun: { accent: "#000000" } } }, 422, "BRD-02", "theme.sun"],
    ["logo exécutable", { logo: { kind: "data_uri", src: "data:text/html;base64,PHNjcmlwdD4=" } }, 422, "BRD-03", "logo"],
    ["domaine déjà déclaré", { custom_domain: TAKEN_DOMAIN }, 409, "BRD-04", "custom_domain"],
    ["domaine réservé (hôte de la plateforme)", { custom_domain: "payer.mulemacare.invalid" }, 422, "BRD-05", "custom_domain"],
  ])("marque refusée (%s) : code stable et champ en défaut", async (_label, change, status, code, field) => {
    const res = await call({ role: "admin", method: "put", template: "/v1/organization/branding", url: "/v1/organization/branding", status, body: brandingBody(change) });
    expect(res.status).toBe(status);
    const body = (await res.json()) as { code: string; errors?: { field: string }[] };
    expect(body.code).toBe(code);
    expect(body.errors?.map((e) => e.field)).toContain(field);
  });

  it("domaine : en attente avec enregistrement TXT, BRD-06 sans preuve, vérifié ensuite ; même domaine garde sa preuve", async () => {
    const put = (domain: string) => call({ role: "admin", method: "put", template: "/v1/organization/branding", url: "/v1/organization/branding", status: 200, body: brandingBody({ custom_domain: domain }) });
    const verify = () => call({ role: "admin", method: "post", template: "/v1/organization/branding/domain-verification", url: "/v1/organization/branding/domain-verification", status: 200 });
    const pending = (await (await put("attente.lagune-sante.ci")).json()) as { custom_domain_status: string; custom_domain_verification: { record_name: string; record_value: string } };
    expect(pending.custom_domain_status).toBe("en_attente_de_verification");
    expect(pending.custom_domain_verification.record_name).toBe("_mulemacare-verification.attente.lagune-sante.ci");
    expect(pending.custom_domain_verification.record_value).toMatch(/^mulemacare-verification=[0-9a-f]{32}$/);
    const refused = await verify();
    expect(refused.status).toBe(422);
    expect(((await refused.json()) as { code: string }).code).toBe("BRD-06");
    const first = (await (await put("sante.lagune-sante.ci")).json()) as { custom_domain_verification: { record_value: string } };
    const proven = (await (await verify()).json()) as { custom_domain_status: string };
    expect(proven.custom_domain_status).toBe("verifie");
    const again = (await (await put("sante.lagune-sante.ci")).json()) as { custom_domain_status: string; custom_domain_verification: { record_value: string } };
    expect(again.custom_domain_status).toBe("verifie");
    expect(again.custom_domain_verification.record_value).toBe(first.custom_domain_verification.record_value);
  });

  it("accueil d'organisation : ORG-01 identifiant pris, ORG-02 gabarit d'un autre pays", async () => {
    const taken = await call({ role: "admin_plateforme", method: "post", template: "/v1/platform/organizations", url: "/v1/platform/organizations", status: 409, body: organizationBody({ slug: "teranga-assurances" }) });
    expect(((await taken.json()) as { code: string }).code).toBe("ORG-01");
    const otherCountry = await call({ role: "admin_plateforme", method: "post", template: "/v1/platform/organizations", url: "/v1/platform/organizations", status: 422, body: organizationBody({ country_code: "SN", template: { code: "mutuelle-ci" } }) });
    expect(((await otherCountry.json()) as { code: string }).code).toBe("ORG-02");
    const created = await call({ role: "admin_plateforme", method: "post", template: "/v1/platform/organizations", url: "/v1/platform/organizations", status: 201, body: organizationBody({ slug: "mutuelle-korhogo" }) });
    const onboarding = (await created.json()) as { template: { version: number }; first_manager: { roles: { role: string }[] } };
    expect(onboarding.template.version).toBe(2);
    expect(onboarding.first_manager.roles.map((r) => r.role)).toEqual(["gestionnaire", "admin"]);
    const again = await call({ role: "admin_plateforme", method: "post", template: "/v1/platform/organizations", url: "/v1/platform/organizations", status: 409, body: organizationBody({ slug: "mutuelle-korhogo" }) });
    expect(again.status).toBe(409);
  });

  it("sans jeton : 401 AUTH-01", async () => {
    const res = await fetch(`${API_BASE_URL}/v1/claims`);
    expect(res.status).toBe(401);
    expect(((await res.json()) as { code: string }).code).toBe("AUTH-01");
  });

  it("jeu de démonstration non vide et cohérent", () => {
    expect(DEMO_CLAIMS.length).toBeGreaterThan(5);
    expect(REVIEW_CLAIM.status).toBe("en_revue");
    expect(AUTO_CLAIM.status).toBe("accordee_auto");
  });
});
