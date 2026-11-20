import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { CONTRACT_PALETTE } from "./contract-palette";
import { BRANDING_FIXTURES } from "./fixtures";
import { GUARDED_TEXT_PAIRS, GUARDED_UI_PAIRS, OVERRIDABLE_TOKENS, STATUS_TOKENS, TEXT_MINIMUM, UI_MINIMUM, brandProblems, effectiveTokens, themeProblems, type BrandTheme } from "./policy";

const here = path.dirname(fileURLToPath(import.meta.url));
const apiPalette = readFileSync(path.resolve(here, "../../../api/branding/palette.py"), "utf8");

function pythonTuple(name: string): string[][] {
  const body = new RegExp(`${name}: Final = \\(([\\s\\S]*?)\\n\\)`).exec(apiPalette)?.[1] ?? new RegExp(`${name}: Final = \\((.*)\\)`).exec(apiPalette)?.[1] ?? "";
  return [...body.matchAll(/\("(--[a-z0-9-]+)", "(--[a-z0-9-]+)"\)/g)].map((m) => [m[1]!, m[2]!]);
}

describe("même politique que l'API (apps/api/branding/palette.py)", () => {
  it("mêmes paires gardées, mêmes seuils, même liste fermée", () => {
    expect(GUARDED_TEXT_PAIRS.map((p) => [...p])).toEqual(pythonTuple("GUARDED_TEXT_PAIRS"));
    expect(GUARDED_UI_PAIRS.map((p) => [...p])).toEqual(pythonTuple("GUARDED_UI_PAIRS"));
    expect(apiPalette).toContain(`OVERRIDABLE_TOKENS: Final = (${OVERRIDABLE_TOKENS.map((t) => `"${t}"`).join(", ")})`);
    expect(apiPalette).toContain(`TEXT_MINIMUM: float = ${TEXT_MINIMUM}`);
    expect(apiPalette).toContain(`UI_MINIMUM: float = ${UI_MINIMUM.toFixed(1)}`);
    expect(apiPalette).toContain(`STATUS_TOKENS: Final = (${STATUS_TOKENS.map((t) => `"${t}"`).join(", ")})`);
  });
});

describe("garde de contraste", () => {
  it("le thème MulemaCare passe, en clair et en sombre", () => {
    expect(brandProblems({})).toEqual([]);
  });

  it("les marques fictives conformes passent ; la marque agressive échoue en clair", () => {
    expect(brandProblems(BRANDING_FIXTURES["lagune-sante"]!.theme as BrandTheme)).toEqual([]);
    expect(brandProblems(BRANDING_FIXTURES["teranga-assurances"]!.theme as BrandTheme)).toEqual([]);
    const problems = brandProblems(BRANDING_FIXTURES["marque-agressive"]!.theme as BrandTheme);
    expect(problems.length).toBeGreaterThan(0);
    expect(new Set(problems.map((p) => p.theme))).toEqual(new Set(["light"]));
    expect(problems.some((p) => p.token === "accent" && p.pair?.[1] === "--surface")).toBe(true);
  });

  it("le focus suit l'accent (3:1 exigé) ; un accent illisible est attribué à l'accent", () => {
    const tokens = effectiveTokens("light", { accent: "#ffd400" });
    expect(tokens["--focus"]).toBe("#ffd400");
    const problems = themeProblems("light", { accent: "#ffd400" });
    expect(problems.some((p) => p.pair?.[0] === "--focus" && p.minimum === UI_MINIMUM)).toBe(true);
    expect(problems.every((p) => p.token === "accent")).toBe(true);
  });

  it("un accent égal à une couleur de statut est refusé (contrat §5)", () => {
    for (const status of STATUS_TOKENS) {
      const color = CONTRACT_PALETTE.light[status]!;
      expect(themeProblems("light", { accent: color }).some((p) => p.kind === "statut")).toBe(true);
    }
  });

  it("la paire en défaut est attribuée au jeton surchargé, pas à son voisin d'origine", () => {
    const problems = themeProblems("light", { accent_fg: "#0a7a6e" });
    expect(problems.length).toBeGreaterThan(0);
    expect(problems.every((p) => p.token === "accent_fg")).toBe(true);
  });
});
