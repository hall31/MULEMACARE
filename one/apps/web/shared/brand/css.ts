/**
 * Feuille de style de la marque : uniquement des variables CSS de la LISTE FERMÉE, valeurs
 * `#rrggbb` revérifiées ici (aucune autre clé, aucun texte libre ne peut entrer dans le CSS).
 *
 * Sélecteurs exclusifs (chaque thème de la marque ne s'applique que dans son thème, quel que soit
 * l'ordre des feuilles), de spécificité 0-3-0, au-dessus des 0-2-0 du contrat, sans `!important` :
 * - clair : système clair hors `data-theme="dark"`, ou `data-theme="light"` ;
 * - sombre : système sombre hors `data-theme="light"`, ou `data-theme="dark"` ;
 * - jamais sous `[data-sun]` (noir sur blanc quel que soit le thème).
 * Le focus suit l'accent (contrat §2).
 */
import { normalizeHex } from "./contrast";
import { OVERRIDABLE_TOKENS, cssName, type BrandTheme, type TokenOverrides } from "./policy";

function declarations(overrides: TokenOverrides | undefined): string {
  if (!overrides) return "";
  const lines: string[] = [];
  for (const token of OVERRIDABLE_TOKENS) {
    const value = normalizeHex(overrides[token]);
    if (!value) continue;
    lines.push(`${cssName(token)}:${value};`);
    if (token === "accent") lines.push(`--focus:${value};`);
  }
  return lines.join("");
}

export const BRAND_LIGHT_SYSTEM_SELECTOR = ':root:not([data-sun]):not([data-theme="dark"])';
export const BRAND_LIGHT_SELECTOR = ':root[data-theme="light"]:not([data-sun])';
export const BRAND_DARK_SYSTEM_SELECTOR = ':root:not([data-sun]):not([data-theme="light"])';
export const BRAND_DARK_SELECTOR = ':root[data-theme="dark"]:not([data-sun])';

/** CSS de la marque ; chaîne vide si rien n'est surchargé. */
export function brandStyleSheet(theme: BrandTheme | null | undefined): string {
  if (!theme) return "";
  const light = declarations(theme.light);
  const dark = declarations(theme.dark);
  const rules: string[] = [];
  if (light) {
    rules.push(`@media not all and (prefers-color-scheme: dark){${BRAND_LIGHT_SYSTEM_SELECTOR}{${light}}}`);
    rules.push(`${BRAND_LIGHT_SELECTOR}{${light}}`);
  }
  if (dark) {
    rules.push(`@media (prefers-color-scheme: dark){${BRAND_DARK_SYSTEM_SELECTOR}{${dark}}}`);
    rules.push(`${BRAND_DARK_SELECTOR}{${dark}}`);
  }
  return rules.join("\n");
}

/** Variables inline d'un aperçu (écran de réglage) : mêmes clés fermées, mêmes valeurs revérifiées. */
export function brandPreviewVariables(overrides: TokenOverrides): Record<string, string> {
  const vars: Record<string, string> = {};
  for (const token of OVERRIDABLE_TOKENS) {
    const value = normalizeHex(overrides[token]);
    if (!value) continue;
    vars[cssName(token)] = value;
    if (token === "accent") vars["--focus"] = value;
  }
  return vars;
}
