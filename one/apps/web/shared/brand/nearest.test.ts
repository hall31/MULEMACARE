import { describe, expect, it } from "vitest";
import { hexToRgb } from "./contrast";
import { CONTRACT_PALETTE } from "./contract-palette";
import { nearestCompliant } from "./nearest";
import { themeProblems } from "./policy";

describe("couleur conforme la plus proche (écran de réglage, BRD-01)", () => {
  it("une couleur déjà conforme est rendue telle quelle", () => {
    expect(nearestCompliant("light", "accent", "#6D2E8C")).toBe("#6d2e8c");
  });

  it("le jaune vif refusé en clair devient une couleur conforme, plus sombre, de même famille", () => {
    const fixed = nearestCompliant("light", "accent", "#ffd400");
    expect(fixed).not.toBeNull();
    expect(themeProblems("light", { accent: fixed! })).toEqual([]);
    const { r, g, b } = hexToRgb(fixed!);
    // Toujours un jaune-brun (rouge et vert au-dessus du bleu), seulement plus sombre.
    expect(r).toBeGreaterThan(b);
    expect(g).toBeGreaterThan(b);
    expect(r + g + b).toBeLessThan(255 + 212);
  });

  it("tient compte des autres jetons du thème (texte sur accent)", () => {
    const fixed = nearestCompliant("light", "accent", "#8fd3c7", { accent_fg: "#ffffff" });
    expect(fixed).not.toBeNull();
    expect(themeProblems("light", { accent: fixed!, accent_fg: "#ffffff" }).filter((p) => p.token === "accent")).toEqual([]);
  });

  it("en sombre, éclaircit un accent trop sombre", () => {
    const fixed = nearestCompliant("dark", "accent", "#123456");
    expect(fixed).not.toBeNull();
    expect(themeProblems("dark", { accent: fixed! })).toEqual([]);
  });

  it("une couleur de statut à l'identique n'est jamais proposée", () => {
    const status = CONTRACT_PALETTE.light["--crit"]!;
    const fixed = nearestCompliant("light", "accent", status);
    expect(fixed).not.toBe(status);
    if (fixed) expect(themeProblems("light", { accent: fixed })).toEqual([]);
  });

  it("une valeur hors format ne produit rien", () => {
    expect(nearestCompliant("light", "accent", "jaune")).toBeNull();
  });
});
