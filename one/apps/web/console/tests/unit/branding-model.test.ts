/** Modèle de l'écran « Marque » (P3) : requête, contraste en direct, suggestion, aperçu, erreurs de l'API. */
import { describe, expect, it } from "vitest";
import { BRANDING_FIXTURES, CONTRACT_PALETTE } from "@shared/brand";
import type { BrandingSettings } from "../../src/api/types";
import { contrastReport, draftErrors, draftFromSettings, effectiveColor, previewVariables, problemFieldErrors, requestFromDraft, suggestionFor } from "../../src/features/branding/branding-model";
import { INITIAL_BRANDING } from "../../src/mocks/platform";

const lagune: BrandingSettings = { ...INITIAL_BRANDING, display_name: "Mutuelle Lagune Santé", theme: BRANDING_FIXTURES["lagune-sante"]!.theme, customized: true };

describe("brouillon et requête updateBrandingSettings", () => {
  it("aller-retour : réglages → brouillon → requête, seulement les jetons saisis", () => {
    const draft = draftFromSettings(lagune);
    expect(draft.colors.dark.accent_fg).toBe("");
    const request = requestFromDraft(draft);
    expect(request.theme).toEqual(BRANDING_FIXTURES["lagune-sante"]!.theme);
    expect(request).toMatchObject({ display_name: "Mutuelle Lagune Santé", custom_domain: null, legal_notice: null });
  });

  it("aucun thème vide n'est envoyé ; une couleur hors format bloque l'envoi sous son champ", () => {
    const draft = draftFromSettings(INITIAL_BRANDING);
    expect(requestFromDraft(draft).theme).toEqual({});
    draft.colors.light.accent = "#12345";
    draft.customDomain = "Pas un domaine";
    expect(draftErrors(draft)).toEqual({ "theme.light.accent": "format", custom_domain: "domain" });
  });
});

describe("contraste en direct (même calcul que l'API)", () => {
  it("thème MulemaCare et marque conforme : toutes les paires passent", () => {
    for (const theme of ["light", "dark"] as const) {
      expect(contrastReport(draftFromSettings(INITIAL_BRANDING), theme).pairs.every((p) => p.ok)).toBe(true);
      expect(contrastReport(draftFromSettings(lagune), theme).problems).toEqual([]);
    }
  });

  it("jaune vif en clair : paires en défaut, couleur conforme la plus proche proposée", () => {
    const draft = draftFromSettings(INITIAL_BRANDING);
    draft.colors.light.accent = "#ffd400";
    const report = contrastReport(draft, "light");
    expect(report.pairs.filter((p) => !p.ok).length).toBeGreaterThan(2);
    const suggestion = suggestionFor(draft, "light", "accent");
    expect(suggestion).toMatch(/^#[0-9a-f]{6}$/);
    draft.colors.light.accent = suggestion!;
    expect(contrastReport(draft, "light").problems).toEqual([]);
    expect(suggestionFor(draft, "light", "accent")).toBeNull();
  });

  it("aperçu : couleurs du contrat + surcharges ; le sélecteur montre la couleur effective", () => {
    const draft = draftFromSettings(lagune);
    const vars = previewVariables(draft, "dark");
    expect(vars["--accent"]).toBe("#d4a8ea");
    expect(vars["--focus"]).toBe("#d4a8ea");
    expect(vars["--bg"]).toBe(CONTRACT_PALETTE.dark["--bg"]);
    expect(effectiveColor(draft, "dark", "accent_fg")).toBe(CONTRACT_PALETTE.dark["--accent-fg"]);
  });
});

it("erreurs de l'API rattachées au champ (BRD-01 par jeton, BRD-03 logo, BRD-04 domaine)", () => {
  expect(problemFieldErrors({ code: "BRD-01", message: "m", action: "a", request_id: "r", errors: [{ field: "theme.light.accent", message: "1,43:1" }] })).toEqual({ "theme.light.accent": ["1,43:1"] });
  expect(problemFieldErrors({ code: "BRD-03", message: "Logo refusé.", action: "a", request_id: "r" })).toEqual({ logo: ["Logo refusé."] });
  expect(problemFieldErrors({ code: "BRD-04", message: "Domaine pris.", action: "a", request_id: "r" })).toEqual({ custom_domain: ["Domaine pris."] });
});
