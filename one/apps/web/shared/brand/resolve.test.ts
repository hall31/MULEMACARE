import { describe, expect, it } from "vitest";
import { BRANDING_FIXTURES } from "./fixtures";
import { DEFAULT_BRAND, resolveBrand } from "./resolve";

const ok = (payload: unknown) => resolveBrand({ status: "ok", payload });
const clone = <T>(v: T): T => structuredClone(v);

describe("moteur de thème par organisation", () => {
  it("sans marque : thème MulemaCare, aucun signalement", () => {
    expect(resolveBrand({ status: "absent" })).toEqual(DEFAULT_BRAND);
  });

  it("API en erreur : thème MulemaCare, repli signalé", () => {
    const brand = resolveBrand({ status: "erreur", detail: "TimeoutError" });
    expect(brand.css).toBe("");
    expect(brand.identity).toBeNull();
    expect(brand.fallback).toEqual({ reason: "erreur", details: ["TimeoutError"] });
  });

  it("marque conforme : nom, logo et jetons appliqués", () => {
    const brand = ok(clone(BRANDING_FIXTURES["lagune-sante"]));
    expect(brand.fallback).toBeNull();
    expect(brand.identity).toMatchObject({ slug: "lagune-sante", displayName: "Mutuelle Lagune Santé", countryCode: "CI" });
    expect(brand.identity?.logoSrc).toMatch(/^data:image\/svg\+xml;base64,/);
    expect(brand.css).toContain("--accent:#6d2e8c;");
    expect(brand.css).toContain("--accent:#d4a8ea;");
  });

  it("marque agressive (échoue AA) : couleurs repliées sur MulemaCare, nom gardé, repli signalé", () => {
    const brand = ok(clone(BRANDING_FIXTURES["marque-agressive"]));
    expect(brand.css).toBe("");
    expect(brand.theme).toBeNull();
    expect(brand.identity?.displayName).toBe("Marque Agressive (test)");
    expect(brand.fallback?.reason).toBe("contraste");
    expect(brand.fallback?.details.join(" ")).toMatch(/light\.accent: --accent \/ --surface = 1\.43:1 < 4\.5:1/);
  });

  it("jeton hors liste fermée ou thème plein soleil : couleurs refusées en bloc", () => {
    const withExtra = clone(BRANDING_FIXTURES["teranga-assurances"]) as unknown as Record<string, unknown>;
    withExtra.theme = { light: { accent: "#0b5f8a", bg: "#000000" }, sun: { accent: "#000000" } };
    const brand = ok(withExtra);
    expect(brand.css).toBe("");
    expect(brand.fallback).toEqual({ reason: "invalide", details: ["theme.light.bg", "theme.sun"] });
    expect(brand.identity?.displayName).toBe("Teranga Assurances");
  });

  it("réponse hors contrat : tout est replié", () => {
    for (const payload of [null, "texte", [], { slug: "X Y", display_name: "a", country_code: "CI", currency: "XOF" }, { slug: "ok-slug", display_name: "", country_code: "CI", currency: "XOF" }, { slug: "ok-slug", display_name: "A", country_code: "FR", currency: "XOF" }]) {
      const brand = ok(payload);
      expect(brand.identity).toBeNull();
      expect(brand.css).toBe("");
      expect(brand.fallback?.reason).toBe("invalide");
    }
  });

  it("le nom affiché reste du texte brut (caractères de contrôle retirés, longueur bornée)", () => {
    const payload = { ...clone(BRANDING_FIXTURES["teranga-assurances"]), display_name: `\u0000<b>Teranga</b>\u0007${"x".repeat(300)}` };
    const brand = ok(payload);
    expect(brand.identity?.displayName.startsWith("<b>Teranga</b>")).toBe(true);
    expect(brand.identity?.displayName.length).toBe(120);
    expect(brand.identity?.displayName).not.toMatch(/[\u0000-\u001f]/);
  });

  it("logo dangereux : écarté, le reste de la marque s'applique", () => {
    const payload = { ...clone(BRANDING_FIXTURES["teranga-assurances"]), logo: { kind: "url", src: "javascript:alert(1)" } };
    const brand = ok(payload);
    expect(brand.identity?.logoSrc).toBeNull();
    expect(brand.css).toContain("--accent:#0b5f8a;");
  });
});
