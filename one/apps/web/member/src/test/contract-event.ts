/**
 * Juge unique d'un événement de mesure (`recordProductEvent`, CR-P2-01/CR-P2-02), partagé par
 * Vitest et Playwright : chaque corps émis est validé contre `ProductEventRequest` tel qu'écrit
 * dans `specs/openapi.yaml` (Ajv, JSON Schema 2020-12 = OpenAPI 3.1), puis contre ce que le
 * schéma ne peut pas porter seul et que l'API refuse en 422 (description de `duration_ms`,
 * `apps/api/metrics/catalog.py`) : durée seulement pour deux événements, avec leur borne, et
 * identifiant de session jamais fait que de chiffres. Fichier de test : jamais importé par l'app.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import { parse } from "yaml";

const here = path.dirname(fileURLToPath(import.meta.url));
const SPEC_PATH = path.resolve(here, "../../../../../specs/openapi.yaml");

interface PropertySchema {
  type?: string;
  pattern?: string;
  minimum?: number;
  maximum?: number;
  description?: string;
}

export const spec = parse(readFileSync(SPEC_PATH, "utf8")) as {
  components: { schemas: Record<string, { enum?: string[]; properties?: Record<string, PropertySchema>; required?: string[] }> };
};

const ajv = new Ajv2020({ strict: false, allErrors: true, validateFormats: false });
ajv.addSchema(spec, "openapi.json");
const validateSchema = ajv.compile({ $ref: "openapi.json#/components/schemas/ProductEventRequest" });

/** Seuls événements qui admettent une durée (CR-P2-02) ; ailleurs l'API répond 422. */
export const CONTRACT_DURATIONS: Readonly<Record<string, { required: boolean; max: number }>> = {
  counter_decision_shown: { required: true, max: 300_000 },
  onboarding_completed: { required: false, max: 3_600_000 },
};

/** Description contractuelle de `duration_ms` (le test vérifie qu'elle dit bien la même chose). */
export function contractDurationProperty(): PropertySchema {
  return spec.components.schemas.ProductEventRequest?.properties?.duration_ms ?? {};
}

/** Problèmes de conformité d'un corps envoyé ; tableau vide : l'API l'accepte. */
export function contractProblems(event: unknown): string[] {
  const problems: string[] = [];
  if (!validateSchema(event)) {
    for (const error of validateSchema.errors ?? []) problems.push(`${error.instancePath || "/"} ${error.message ?? ""}`.trim());
    return problems;
  }
  const body = event as { name: string; session_id: string; duration_ms?: number };
  const rule = CONTRACT_DURATIONS[body.name];
  if (body.duration_ms !== undefined) {
    if (!rule) problems.push(`${body.name} n'admet aucune durée`);
    else if (body.duration_ms > rule.max) problems.push(`${body.name} : durée de ${rule.max} ms au plus`);
  } else if (rule?.required) problems.push(`${body.name} : durée exigée`);
  if (/^[0-9]+$/.test(body.session_id)) problems.push("session_id fait que de chiffres");
  return problems;
}
