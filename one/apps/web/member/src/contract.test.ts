import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { parse } from "yaml";
import * as fixtures from "@/test/fixtures";

/**
 * Secret médical (AGENTS.md) : l'espace adhérent n'affiche aucune donnée médicale, aucun score,
 * aucune règle interne. Le contrat P1 n'en renvoie pas ; ce test le vérifie sur le contrat
 * lui-même ET sur chaque donnée simulée servie à l'interface (mocks Playwright compris).
 */
const here = path.dirname(fileURLToPath(import.meta.url));
const spec = parse(readFileSync(path.join(here, "../../../../specs/openapi.yaml"), "utf8")) as OpenApi;

interface SchemaObject {
  $ref?: string;
  type?: string | string[];
  properties?: Record<string, SchemaObject>;
  required?: string[];
  items?: SchemaObject;
  oneOf?: SchemaObject[];
  enum?: unknown[];
  const?: unknown;
}
interface OpenApi {
  paths: Record<string, Record<string, { operationId?: string; "x-lot"?: string; responses?: Record<string, { content?: Record<string, { schema?: SchemaObject }> }> }>>;
  components: { schemas: Record<string, SchemaObject> };
}

/** Mots qui trahiraient une donnée médicale, un score ou une règle interne (FR + EN). */
const FORBIDDEN_KEY = /diagnos|medical|m[ée]dic|motif|reason_text|ordonnance|prescription|patholog|symptom|act_code|^acts?$|^items_?detail|fraud|score|risk|alert|check|evaluation|trace|review|healthos|fhir|decided_by|author|note/i;

function resolve(schema: SchemaObject): SchemaObject {
  if (!schema.$ref) return schema;
  const name = schema.$ref.replace("#/components/schemas/", "");
  const found = spec.components.schemas[name];
  if (!found) throw new Error(`schéma introuvable : ${schema.$ref}`);
  return resolve(found);
}

/** Toutes les clés que le contrat peut renvoyer sous ce schéma (récursif). */
function contractKeys(schema: SchemaObject, seen = new Set<string>()): string[] {
  const s = resolve(schema);
  const keys: string[] = [];
  for (const [key, child] of Object.entries(s.properties ?? {})) {
    keys.push(key);
    const marker = JSON.stringify(child);
    if (seen.has(marker)) continue;
    seen.add(marker);
    keys.push(...contractKeys(child, seen));
  }
  if (s.items) keys.push(...contractKeys(s.items, seen));
  for (const variant of s.oneOf ?? []) keys.push(...contractKeys(variant, seen));
  return keys;
}

/** Vérifie qu'une valeur respecte le schéma : aucune clé en plus, toutes les clés requises présentes. */
function conformance(value: unknown, schema: SchemaObject, where: string): string[] {
  const s = resolve(schema);
  if (s.oneOf) {
    const results = s.oneOf.map((variant) => conformance(value, variant, where));
    return results.some((r) => r.length === 0) ? [] : (results[0] ?? []);
  }
  const types = Array.isArray(s.type) ? s.type : s.type ? [s.type] : [];
  if (value === null) return types.includes("null") ? [] : [`${where} : null non autorisé`];
  if (s.enum && !s.enum.includes(value)) return [`${where} : ${JSON.stringify(value)} hors enum`];
  if (Array.isArray(value)) return s.items ? value.flatMap((v, i) => conformance(v, s.items as SchemaObject, `${where}[${i}]`)) : [];
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const props = s.properties ?? {};
    const extra = Object.keys(record).filter((k) => !(k in props)).map((k) => `${where}.${k} : hors contrat`);
    const missing = (s.required ?? []).filter((k) => !(k in record)).map((k) => `${where}.${k} : requis absent`);
    const nested = Object.entries(record).flatMap(([k, v]) => (props[k] ? conformance(v, props[k], `${where}.${k}`) : []));
    return [...extra, ...missing, ...nested];
  }
  if (typeof value === "number" && types.includes("integer") && !Number.isSafeInteger(value)) return [`${where} : entier attendu`];
  return [];
}

function responseSchema(operationId: string, status: string): SchemaObject {
  for (const operations of Object.values(spec.paths)) {
    for (const op of Object.values(operations)) {
      if (op.operationId !== operationId) continue;
      const schema = op.responses?.[status]?.content?.["application/json"]?.schema;
      if (!schema) throw new Error(`${operationId} ${status} sans schéma JSON`);
      return schema;
    }
  }
  throw new Error(`opération inconnue : ${operationId}`);
}

/** Opérations consommées par l'espace adhérent et la page publique du payeur. */
const CONSUMED = {
  getCurrentUser: "200",
  getMyCard: "200",
  listMyBeneficiaries: "200",
  listMyClaims: "200",
  getMyClaimTracking: "200",
  listMyContributions: "200",
  createMyPaymentLink: "201",
  getPublicPaymentLink: "200",
  startCheckout: "201",
} as const;

describe("contrat P1 : aucune donnée médicale, aucun score, aucune règle interne", () => {
  it("les opérations P1 du contrat sont toutes consommées par l'espace", () => {
    const p1 = Object.values(spec.paths)
      .flatMap((ops) => Object.values(ops))
      .filter((op) => op["x-lot"] === "P1")
      .map((op) => op.operationId);
    expect(p1.sort()).toEqual(["createMyPaymentLink", "getMyCard", "getMyClaimTracking", "listMyBeneficiaries", "listMyClaims", "listMyContributions"]);
    for (const id of p1) expect(Object.keys(CONSUMED)).toContain(id);
  });

  it("aucune clé médicale, de score ou de règle interne dans les réponses consommées", () => {
    for (const [operationId, status] of Object.entries(CONSUMED)) {
      const keys = contractKeys(responseSchema(operationId, status));
      expect(keys.length, operationId).toBeGreaterThan(0);
      expect(keys.filter((k) => FORBIDDEN_KEY.test(k)), operationId).toEqual([]);
    }
  });

  it("chaque donnée simulée est conforme au contrat, sans clé en plus", () => {
    const cases: [unknown, string, string][] = [
      [fixtures.me, "getCurrentUser", "200"],
      [fixtures.card, "getMyCard", "200"],
      [fixtures.cardKouassi, "getMyCard", "200"],
      [fixtures.beneficiaries, "listMyBeneficiaries", "200"],
      [{ items: fixtures.claims, page: { next_cursor: null } }, "listMyClaims", "200"],
      ...Object.values(fixtures.trackings).map((t): [unknown, string, string] => [t, "getMyClaimTracking", "200"]),
      [fixtures.contributions, "listMyContributions", "200"],
      [fixtures.publicLink, "getPublicPaymentLink", "200"],
    ];
    for (const [value, operationId, status] of cases) expect(conformance(value, responseSchema(operationId, status), operationId)).toEqual([]);
  });

  it("aucune clé interdite dans les données simulées, à toute profondeur", () => {
    const offenders: string[] = [];
    const walk = (value: unknown, where: string) => {
      if (Array.isArray(value)) value.forEach((v, i) => walk(v, `${where}[${i}]`));
      else if (value && typeof value === "object") {
        for (const [k, v] of Object.entries(value)) {
          if (FORBIDDEN_KEY.test(k)) offenders.push(`${where}.${k}`);
          walk(v, `${where}.${k}`);
        }
      }
    };
    walk(fixtures, "fixtures");
    expect(offenders).toEqual([]);
  });

  it("seul le code public de la règle sort (R-12 v3), jamais sa trace", () => {
    const rules = [...fixtures.claims.map((c) => c.rule), ...Object.values(fixtures.trackings).flatMap((t) => t.steps.map((s) => s.rule))].filter(Boolean);
    expect(rules.length).toBeGreaterThan(0);
    for (const rule of rules) expect(Object.keys(rule ?? {}).sort()).toEqual(["code", "version"]);
  });
});
