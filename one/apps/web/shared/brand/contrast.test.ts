import { describe, expect, it } from "vitest";
import { contrastRatio, hexToRgb, normalizeHex, rgbToHex } from "./contrast";
import { CONTRACT_PALETTE } from "./contract-palette";

const L = CONTRACT_PALETTE.light;
const D = CONTRACT_PALETTE.dark;
const r2 = (a: string | undefined, b: string | undefined) => Math.round(contrastRatio(a ?? "", b ?? "") * 100) / 100;

describe("contraste WCAG (même formule que apps/api/branding/contrast.py)", () => {
  it("retrouve le tableau §3 du contrat de design", () => {
    expect(r2(L["--accent"], L["--surface"])).toBe(5.8);
    expect(r2(D["--accent"], D["--surface"])).toBe(7.97);
    expect(r2(L["--accent-fg"], L["--accent-hover"])).toBe(7.65);
    expect(r2(L["--brand-gold"], L["--surface"])).toBe(3.19);
    expect(r2(L["--fg"], L["--bg"])).toBe(16.88);
  });

  it("est symétrique et borné de 1 à 21", () => {
    expect(contrastRatio(L["--fg"]!, L["--bg"]!)).toBe(contrastRatio(L["--bg"]!, L["--fg"]!));
    expect(r2(L["--surface"], L["--surface"])).toBe(1);
  });

  it("n'accepte que #rrggbb (ni nom, ni rgb(), ni CSS)", () => {
    expect(normalizeHex(L["--accent"]?.toUpperCase())).toBe(L["--accent"]);
    for (const bad of ["red", "rgb(0,0,0)", "#fff", "#12345g", "#123456;}body{", "", null, 12]) expect(normalizeHex(bad)).toBeNull();
    expect(() => hexToRgb("bleu")).toThrow();
    expect(rgbToHex(hexToRgb(L["--accent"]!))).toBe(L["--accent"]);
  });
});
