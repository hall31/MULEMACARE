import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";
import { CONTRACT_PALETTE } from "./contract-palette";
import { parseTokenCss } from "./tokens";

const here = path.dirname(fileURLToPath(import.meta.url));
const tokensCss = readFileSync(path.resolve(here, "../../../../specs/design/mulemacare-tokens.css"), "utf8");

it("le miroir des couleurs est identique à specs/design/mulemacare-tokens.css (node scripts/gen-contract-palette.mjs)", () => {
  expect(CONTRACT_PALETTE).toEqual(parseTokenCss(tokensCss));
});

it("lit les deux thèmes et les jetons gardés", () => {
  for (const theme of ["light", "dark"] as const) {
    for (const token of ["--bg", "--surface", "--accent", "--accent-hover", "--accent-2", "--accent-fg", "--focus", "--ok", "--warn", "--crit", "--info", "--brand-deep", "--brand-on-deep", "--brand-on-deep-2"]) {
      expect(CONTRACT_PALETTE[theme][token], `${theme} ${token}`).toMatch(/^#[0-9a-f]{6}$/);
    }
  }
  expect(CONTRACT_PALETTE.dark["--accent"]).not.toBe(CONTRACT_PALETTE.light["--accent"]);
  // Le sombre hérite du clair pour ce qu'il ne redéclare pas (comme la cascade CSS).
  expect(CONTRACT_PALETTE.dark["--brand-on-deep"]).toBe(CONTRACT_PALETTE.light["--brand-on-deep"]);
});
