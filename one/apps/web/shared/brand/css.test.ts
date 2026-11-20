import { describe, expect, it } from "vitest";
import { brandPreviewVariables, brandStyleSheet } from "./css";
import type { BrandTheme } from "./policy";

describe("feuille de style de la marque", () => {
  it("rien à surcharger : rien d'injecté", () => {
    expect(brandStyleSheet(null)).toBe("");
    expect(brandStyleSheet({})).toBe("");
    expect(brandStyleSheet({ light: {} })).toBe("");
  });

  it("n'écrit que les jetons de la liste fermée, le focus suit l'accent", () => {
    const css = brandStyleSheet({ light: { accent: "#6D2E8C", brand_deep: "#3f1a52" } });
    expect(css).toContain("--accent:#6d2e8c;");
    expect(css).toContain("--focus:#6d2e8c;");
    expect(css).toContain("--brand-deep:#3f1a52;");
    const declared = [...css.matchAll(/(--[a-z-]+):/g)].map((m) => m[1]);
    expect(new Set(declared)).toEqual(new Set(["--accent", "--focus", "--brand-deep"]));
  });

  it("aucune clé hors liste ni valeur hors format ne passe (pas de CSS libre)", () => {
    const hostile = {
      light: { accent: "#123456;}body{display:none", bg: "#000000", "accent_fg": "red", "x}{": "#000000" },
      sun: { accent: "#000000" },
    } as unknown as BrandTheme;
    expect(brandStyleSheet(hostile)).toBe("");
  });

  it("jamais sous le plein soleil ; clair et sombre exclusifs", () => {
    const css = brandStyleSheet({ light: { accent: "#6d2e8c" }, dark: { accent: "#d4a8ea" } });
    const selectors = [...css.matchAll(/(:root[^{]*)\{--/g)].map((m) => m[1]!);
    expect(selectors.length).toBe(4);
    for (const selector of selectors) expect(selector).toContain(":not([data-sun])");
    expect(css).toMatch(/@media not all and \(prefers-color-scheme: dark\)\{:root:not\(\[data-sun\]\):not\(\[data-theme="dark"\]\)\{--accent:#6d2e8c;/);
    expect(css).toMatch(/:root\[data-theme="light"\]:not\(\[data-sun\]\)\{--accent:#6d2e8c;/);
    expect(css).toMatch(/@media \(prefers-color-scheme: dark\)\{:root:not\(\[data-sun\]\):not\(\[data-theme="light"\]\)\{--accent:#d4a8ea;/);
    expect(css).toMatch(/:root\[data-theme="dark"\]:not\(\[data-sun\]\)\{--accent:#d4a8ea;/);
  });

  it("variables d'aperçu : mêmes clés fermées", () => {
    expect(brandPreviewVariables({ accent: "#6d2e8c", accent_fg: "nope" })).toEqual({ "--accent": "#6d2e8c", "--focus": "#6d2e8c" });
  });
});
