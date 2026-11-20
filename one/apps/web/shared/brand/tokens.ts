/**
 * Lecture des couleurs du contrat de design (`specs/design/mulemacare-tokens.css`) : thème clair
 * (`:root`) et thème sombre (`:root[data-theme="dark"]`, posé sur le clair). Seules les couleurs
 * `#rrggbb` sont retenues (ombres et voiles en rgba() ne servent à aucun calcul de contraste).
 * Le plein soleil n'est pas lu : il ne se surcharge pas (POLISH_CONTRACT §9, Q-P3-09).
 */
import { normalizeHex } from "./contrast";

export type ThemeName = "light" | "dark";
export type TokenMap = Readonly<Record<string, string>>;
export type ContractPalette = Readonly<Record<ThemeName, TokenMap>>;

function block(css: string, selector: RegExp): string {
  return selector.exec(css)?.[1] ?? "";
}

function colors(body: string): Record<string, string> {
  const found: Record<string, string> = {};
  for (const match of body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    const value = normalizeHex(match[2]?.trim());
    if (match[1] && value) found[match[1]] = value;
  }
  return found;
}

/** Couleurs des thèmes clair et sombre, telles que le contrat les déclare. */
export function parseTokenCss(css: string): { light: Record<string, string>; dark: Record<string, string> } {
  const light = colors(block(css, /(?:^|\n)\s*:root\s*\{([^}]*)\}/));
  const dark = { ...light, ...colors(block(css, /:root\[data-theme="dark"\]\s*\{([^}]*)\}/)) };
  return { light, dark };
}
