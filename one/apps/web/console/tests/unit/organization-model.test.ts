/** Formulaire « Accueillir une organisation » (P3) : validation, requête, gabarits du pays, ORG-01/02. */
import { describe, expect, it } from "vitest";
import { EMPTY_ORGANIZATION, organizationErrors, organizationRequest, problemErrors, templateChoices } from "../../src/features/platform/organization-model";
import { DEMO_TEMPLATES } from "../../src/mocks/platform";

const filled = { ...EMPTY_ORGANIZATION, slug: "mutuelle-bouake", name: "Mutuelle de Bouaké", managerName: "Adjoua Kouamé", managerSubject: "idp|1", template: "mutuelle-ci@2" };

describe("organisation", () => {
  it("gabarits du même pays seulement, dernière version d'abord", () => {
    expect(templateChoices(DEMO_TEMPLATES, "CI").map((c) => c.value)).toEqual(["mutuelle-ci@2", "mutuelle-ci@1"]);
    expect(templateChoices(DEMO_TEMPLATES, "SN").map((c) => c.value)).toEqual(["mutuelle-sn@1"]);
  });

  it("validation avant envoi : identifiant, champs obligatoires, capacités, e-mail, gabarit", () => {
    expect(organizationErrors(filled, templateChoices(DEMO_TEMPLATES, "CI"))).toEqual({});
    const bad = { ...filled, slug: "-Bouaké", capabilities: [], managerEmail: "pas-un-mail", country: "SN" as const };
    expect(organizationErrors(bad, templateChoices(DEMO_TEMPLATES, "SN"))).toEqual({ slug: "slug", capabilities: "capabilities", "first_manager.email": "email", template: "template" });
  });

  it("requête conforme au contrat (e-mail omis s'il est vide, version du gabarit explicite)", () => {
    expect(organizationRequest(filled)).toEqual({
      slug: "mutuelle-bouake",
      name: "Mutuelle de Bouaké",
      country_code: "CI",
      capabilities: ["porteur_de_risque", "gestionnaire"],
      regulator: null,
      first_manager: { idp_subject: "idp|1", display_name: "Adjoua Kouamé" },
      template: { code: "mutuelle-ci", version: 2 },
    });
  });

  it("ORG-01 sous l'identifiant, ORG-02 sous le gabarit, VAL-01 sous chaque champ", () => {
    expect(problemErrors({ code: "ORG-01", message: "Identifiant pris.", action: "a", request_id: "r" })).toEqual({ slug: "Identifiant pris." });
    expect(problemErrors({ code: "ORG-02", message: "Gabarit inconnu.", action: "a", request_id: "r" })).toEqual({ template: "Gabarit inconnu." });
    expect(problemErrors({ code: "VAL-01", message: "m", action: "a", request_id: "r", errors: [{ field: "first_manager.email", message: "E-mail." }, { field: "template.code", message: "Code." }] })).toEqual({ "first_manager.email": "E-mail.", template: "Code." });
  });
});
