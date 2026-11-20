// Régénère brand/contract-palette.ts depuis specs/design/mulemacare-tokens.css (même lecture que
// brand/tokens.ts ; brand/contract-palette.test.ts vérifie que le miroir est à jour).
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const css = readFileSync(path.resolve(here, "../../../../specs/design/mulemacare-tokens.css"), "utf8");
const hex = (v) => (/^#[0-9a-fA-F]{6}$/.test(v) ? v.toLowerCase() : null);
const colors = (body) =>
  Object.fromEntries([...body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], hex(m[2].trim())]).filter(([, v]) => v));
const light = colors(/(?:^|\n)\s*:root\s*\{([^}]*)\}/.exec(css)?.[1] ?? "");
const dark = { ...light, ...colors(/:root\[data-theme="dark"\]\s*\{([^}]*)\}/.exec(css)?.[1] ?? "") };
const fmt = (m) => Object.entries(m).map(([k, v]) => `    "${k}": "${v}",`).join("\n");

writeFileSync(
  path.resolve(here, "../brand/contract-palette.ts"),
  `/**
 * Miroir des couleurs de \`specs/design/mulemacare-tokens.css\` (thèmes clair et sombre), pour le
 * calcul de contraste côté navigateur (aperçu en direct, garde de la marque) où le fichier CSS
 * n'est pas lisible. Ce n'est pas du code de composant : l'interface lit les variables CSS, jamais
 * ces valeurs. Tenu identique au contrat par \`contract-palette.test.ts\` (comme
 * \`apps/api/branding/palette.py\` côté serveur) : un jeton modifié sans régénération casse le test.
 * Fichier généré : \`node scripts/gen-contract-palette.mjs\`.
 */
import type { ContractPalette } from "./tokens";

export const CONTRACT_PALETTE: ContractPalette = {
  light: {
${fmt(light)}
  },
  dark: {
${fmt(dark)}
  },
};
`,
);
