/**
 * Mocks « issus de l'OpenAPI » : chaque route simulée existe dans specs/openapi.yaml, chaque réponse
 * (succès et erreurs, par rôle) est validée contre le schéma du contrat ; le CSV d'export suit les
 * colonnes du contrat et neutralise les formules.
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
import { addDays, insurerPortfolio, portfolioCsv, today } from "../../src/mocks/data";
import { handledOperations } from "../../src/mocks/handlers";

const here = path.dirname(fileURLToPath(import.meta.url));
type Json = Record<string, unknown>;
const spec = parse(readFileSync(path.resolve(here, "../../../../../specs/openapi.yaml"), "utf8")) as Json & { paths: Record<string, Record<string, Json>> };
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
ajv.addFormat("int64", true);
ajv.addSchema(spec, "openapi.json");

function schemaRef(template: string, status: number): { ref: string; mediaType: string } {
  const op = spec.paths[template]?.get;
  if (!op) throw new Error(`Opération absente du contrat : GET ${template}`);
  const raw = (op.responses as Record<string, Json>)[String(status)];
  if (!raw) throw new Error(`Statut ${status} non prévu pour GET ${template}`);
  let response = raw;
  if (typeof raw.$ref === "string") {
    let cur: unknown = spec;
    for (const part of raw.$ref.replace(/^#\//, "").split("/")) cur = (cur as Json)[part];
    response = cur as Json;
  }
  const mediaType = Object.keys(response.content as Json)[0]!;
  const media = mediaType.replace("/", "~1");
  const encoded = template.replaceAll("/", "~1");
  const pointer = typeof raw.$ref === "string" ? `${raw.$ref}/content/${media}/schema` : `#/paths/${encoded}/get/responses/${status}/content/${media}/schema`;
  return { ref: `openapi.json${pointer}`, mediaType };
}

const from = addDays(today(), -29);
const cases: { role: DemoRole; template: string; url: string; status: number }[] = [
  { role: "assureur", template: "/v1/me", url: "/v1/me", status: 200 },
  { role: "employeur", template: "/v1/me", url: "/v1/me", status: 200 },
  { role: "assureur", template: "/v1/insurer/portfolio", url: "/v1/insurer/portfolio", status: 200 },
  { role: "assureur", template: "/v1/insurer/portfolio", url: `/v1/insurer/portfolio?from=${from}&to=${today()}`, status: 200 },
  { role: "assureur", template: "/v1/insurer/portfolio", url: `/v1/insurer/portfolio?from=${addDays(today(), -6)}&to=${today()}`, status: 200 },
  { role: "assureur", template: "/v1/insurer/portfolio", url: `/v1/insurer/portfolio?from=${addDays(today(), 10)}&to=${addDays(today(), 20)}`, status: 422 },
  { role: "assureur", template: "/v1/insurer/portfolio", url: "/v1/insurer/portfolio?from=2026-01-10&to=2026-01-01", status: 422 },
  { role: "employeur", template: "/v1/insurer/portfolio", url: "/v1/insurer/portfolio", status: 403 },
  { role: "employeur", template: "/v1/insurer/portfolio/export", url: "/v1/insurer/portfolio/export", status: 403 },
  { role: "employeur", template: "/v1/employer/consumption", url: "/v1/employer/consumption", status: 200 },
  { role: "employeur", template: "/v1/employer/consumption", url: `/v1/employer/consumption?from=${addDays(today(), -364)}&to=${today()}`, status: 200 },
  { role: "assureur", template: "/v1/employer/consumption", url: "/v1/employer/consumption", status: 403 },
  { role: "employeur", template: "/v1/employer/contracts", url: "/v1/employer/contracts", status: 200 },
  { role: "employeur", template: "/v1/employer/contracts", url: "/v1/employer/contracts?within_days=365", status: 200 },
  { role: "employeur", template: "/v1/employer/contracts", url: "/v1/employer/contracts?within_days=0", status: 422 },
];

const call = (role: DemoRole | null, url: string) => fetch(`${API_BASE_URL}${url}`, { headers: role ? { Authorization: `Bearer ${demoToken(role)}` } : {} });

describe("mocks conformes à specs/openapi.yaml", () => {
  it("ne simule que des opérations du contrat, avec les rôles x-roles", () => {
    for (const op of handledOperations) expect(spec.paths[op.path]?.[op.method], op.path).toBeDefined();
    expect(handledOperations.map((o) => o.path)).toEqual(expect.arrayContaining(["/v1/insurer/portfolio", "/v1/insurer/portfolio/export", "/v1/employer/consumption", "/v1/employer/contracts"]));
  });

  it.each(cases.map((c) => [`${c.role} GET ${c.url} → ${c.status}`, c] as const))("%s", async (_label, c) => {
    const res = await call(c.role, c.url);
    expect(res.status).toBe(c.status);
    const { ref, mediaType } = schemaRef(c.template, c.status);
    expect(res.headers.get("content-type") ?? "").toContain(mediaType);
    const validate = ajv.compile({ $ref: ref });
    const body: unknown = await res.json();
    validate(body);
    expect(validate.errors ?? [], JSON.stringify(body).slice(0, 300)).toEqual([]);
  });

  it("export CSV : text/csv, colonnes du contrat, cellules masquées vides", async () => {
    const res = await call("assureur", `/v1/insurer/portfolio/export?from=${addDays(today(), -6)}&to=${today()}`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/csv");
    const lines = (await res.text()).trim().split("\r\n");
    expect(lines[0]).toBe("section;cle;statut;valeur;effectif;unite");
    const masked = lines.filter((l) => l.split(";")[2] === "masque");
    expect(masked.length).toBeGreaterThan(0);
    for (const line of masked) expect(line.split(";").slice(3, 5)).toEqual(["", ""]);
  });

  it("export CSV : une cellule de texte qui commencerait par = + - @ est neutralisée", () => {
    const p = insurerPortfolio(addDays(today(), -29), today());
    p.top_providers[0] = { ...p.top_providers[0]!, name: "=HYPERLINK(\"http://x\")" };
    expect(portfolioCsv(p)).toContain(";'=HYPERLINK");
  });

  it("sans jeton : 401 AUTH-01", async () => {
    const res = await call(null, "/v1/insurer/portfolio");
    expect(res.status).toBe(401);
  });
});

describe("k-anonymat des données de démonstration (mêmes règles que l'API)", () => {
  it("CR-P3-02 : comptes au plancher du palier, montants au millier, période publiée en semaines terminées", () => {
    const p = insurerPortfolio(addDays(today(), -29), today());
    for (const v of [p.members_total, ...p.members_by_status.map((s) => s.count), ...p.benefits_by_category.map((c) => c.claims)]) if (v.value !== null) expect([5, 10, 20, 50, 100]).toContain(v.value);
    for (const v of [p.premiums_xof, p.claims_cost_xof, ...p.benefits_by_category.map((c) => c.covered_xof)]) if (v.value !== null) expect(v.value % 1000).toBe(0);
  });

  it("jamais d'effectif sous le seuil ni hors palier ; masqué = ni valeur ni effectif", () => {
    const values = JSON.stringify([insurerPortfolio(addDays(today(), -6), today()), insurerPortfolio(addDays(today(), -364), today())]);
    for (const m of values.matchAll(/"contributors":(\d+|null)/g)) expect(["5", "10", "20", "50", "100", "null"]).toContain(m[1]);
    expect(values).not.toMatch(/"status":"masque","value":\d/);
  });

  it("statuts : masque complémentaire (suspendus 4 personnes → les en carence aussi)", () => {
    const p = insurerPortfolio(addDays(today(), -29), today());
    expect(p.members_by_status.map((s) => [s.status, s.count.status])).toEqual([["actif", "disponible"], ["carence", "masque"], ["suspendu", "masque"]]);
  });

  it("période courte : petites catégories fondues dans « autres », jamais citées", () => {
    const p = insurerPortfolio(addDays(today(), -6), today());
    const keys = p.benefits_by_category.map((c) => c.category);
    expect(keys).toContain("autres_regroupes");
    expect(keys).not.toContain("maternite");
    expect(keys).not.toContain("hospitalisation");
  });
});
