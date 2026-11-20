/**
 * Modèle du formulaire « Accueillir une organisation » (P3, `createOrganization`), sans React :
 * brouillon, validation avant envoi (mêmes formes que le contrat), requête, gabarits du pays,
 * erreurs de l'API rattachées à leur champ (ORG-01 → identifiant, ORG-02 → gabarit, VAL-01 → champ).
 */
import type { ConfigurationTemplate, CountryCode, CreateOrganizationRequest, OrganizationCapability, Problem } from "@/api/types";

export interface OrganizationDraft {
  slug: string;
  name: string;
  country: CountryCode;
  capabilities: OrganizationCapability[];
  regulator: string;
  managerSubject: string;
  managerName: string;
  managerEmail: string;
  /** `code@version` du gabarit choisi. */
  template: string;
}

export const EMPTY_ORGANIZATION: OrganizationDraft = {
  slug: "",
  name: "",
  country: "CI",
  capabilities: ["porteur_de_risque", "gestionnaire"],
  regulator: "",
  managerSubject: "",
  managerName: "",
  managerEmail: "",
  template: "",
};

export type OrganizationErrorKey = "slug" | "required" | "capabilities" | "email" | "regulator" | "template";

const SLUG = /^[a-z0-9][a-z0-9-]{1,62}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export interface TemplateChoice {
  value: string;
  template: ConfigurationTemplate;
}

/** Gabarits du pays (copie vers une organisation du même pays seulement, Q-P3-04), récents d'abord. */
export function templateChoices(templates: ConfigurationTemplate[], country: CountryCode): TemplateChoice[] {
  return templates
    .filter((tpl) => tpl.country_code === country)
    .sort((a, b) => a.code.localeCompare(b.code) || b.version - a.version)
    .map((template) => ({ value: `${template.code}@${template.version}`, template }));
}

export function organizationErrors(draft: OrganizationDraft, choices: TemplateChoice[]): Record<string, OrganizationErrorKey> {
  const errors: Record<string, OrganizationErrorKey> = {};
  if (!draft.name.trim() || draft.name.length > 120) errors.name = "required";
  if (!SLUG.test(draft.slug)) errors.slug = "slug";
  if (draft.capabilities.length < 1) errors.capabilities = "capabilities";
  if (draft.regulator.length > 40) errors.regulator = "regulator";
  if (!draft.managerName.trim() || draft.managerName.length > 120) errors["first_manager.display_name"] = "required";
  if (!draft.managerSubject.trim() || draft.managerSubject.length > 200) errors["first_manager.idp_subject"] = "required";
  if (draft.managerEmail.trim() && !EMAIL.test(draft.managerEmail.trim())) errors["first_manager.email"] = "email";
  if (!choices.some((c) => c.value === draft.template)) errors.template = "template";
  return errors;
}

export function organizationRequest(draft: OrganizationDraft): CreateOrganizationRequest {
  const [code = "", version] = draft.template.split("@");
  const email = draft.managerEmail.trim();
  return {
    slug: draft.slug,
    name: draft.name.trim(),
    country_code: draft.country,
    capabilities: draft.capabilities,
    regulator: draft.regulator.trim() || null,
    first_manager: { idp_subject: draft.managerSubject.trim(), display_name: draft.managerName.trim(), ...(email ? { email } : {}) },
    template: { code, ...(version ? { version: Number(version) } : {}) },
  };
}

/** Message de l'API sous le champ concerné. */
export function problemErrors(problem: Problem | null): Record<string, string> {
  const byField: Record<string, string> = {};
  if (!problem) return byField;
  for (const error of problem.errors ?? []) {
    const field = error.field.startsWith("template") ? "template" : error.field;
    byField[field] = byField[field] ? `${byField[field]} ${error.message}` : error.message;
  }
  if (problem.code === "ORG-01") byField.slug = problem.message;
  if (problem.code === "ORG-02") byField.template = problem.message;
  return byField;
}
