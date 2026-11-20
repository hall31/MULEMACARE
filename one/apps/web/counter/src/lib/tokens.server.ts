import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * Lit les valeurs des jetons du thème clair dans specs/design/mulemacare-tokens.css.
 * Sert uniquement là où une variable CSS est impossible (manifeste PWA, meta theme-color) :
 * aucune couleur n'est recopiée dans le code.
 */
const TOKENS_PATH = path.join(process.cwd(), "../../../specs/design/mulemacare-tokens.css");

export function lightToken(name: "bg" | "surface" | "accent" | "accent-fg" | "fg"): string {
  const css = readFileSync(TOKENS_PATH, "utf8");
  const root = /:root\s*\{([^}]*)\}/.exec(css)?.[1] ?? "";
  const value = new RegExp(`--${name}:\\s*([^;]+);`).exec(root)?.[1]?.trim();
  if (!value) throw new Error(`Jeton --${name} introuvable dans ${TOKENS_PATH}`);
  return value;
}
