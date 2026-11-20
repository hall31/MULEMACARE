/**
 * Politique de la marque blanche (CR-P3-01, Q-P3-09), miroir de `apps/api/branding/palette.py`.
 *
 * Une organisation ne propose pas un thème : elle surcharge une LISTE FERMÉE de jetons, en clair et
 * en sombre seulement (le plein soleil reste noir sur blanc). Le focus suit l'accent. Chaque paire
 * du contrat de design qui touche un jeton surchargeable est recalculée : texte 4,5:1, repère
 * d'interface (focus) 3:1 ; un accent égal à une couleur de statut est refusé (POLISH_CONTRACT §5).
 * Les listes de paires sont tenues identiques à celles de l'API par `policy.test.ts`.
 */
import { contrastRatio, normalizeHex } from "./contrast";
import { CONTRACT_PALETTE } from "./contract-palette";
import type { ContractPalette, ThemeName } from "./tokens";

export const THEMES: readonly ThemeName[] = ["light", "dark"];
export const OVERRIDABLE_TOKENS = ["accent", "accent_hover", "accent_fg", "brand_deep"] as const;
export type OverridableToken = (typeof OVERRIDABLE_TOKENS)[number];
export type TokenOverrides = Partial<Record<OverridableToken, string>>;
export type BrandTheme = Partial<Record<ThemeName, TokenOverrides>>;

export const TEXT_MINIMUM = 4.5;
export const UI_MINIMUM = 3;
export const STATUS_TOKENS = ["--ok", "--warn", "--crit", "--info"] as const;

export type TokenPair = readonly [foreground: string, background: string];

export const GUARDED_TEXT_PAIRS: readonly TokenPair[] = [
  ["--accent", "--bg"],
  ["--accent", "--surface"],
  ["--accent", "--accent-2"],
  ["--accent-fg", "--accent"],
  ["--accent-fg", "--accent-hover"],
  ["--brand-on-deep", "--brand-deep"],
  ["--brand-on-deep-2", "--brand-deep"],
];
export const GUARDED_UI_PAIRS: readonly TokenPair[] = [
  ["--focus", "--surface"],
  ["--focus", "--bg"],
];

export function isOverridableToken(value: string): value is OverridableToken {
  return (OVERRIDABLE_TOKENS as readonly string[]).includes(value);
}

/** `accent_hover` → `--accent-hover`. */
export function cssName(token: OverridableToken): string {
  return `--${token.replace(/_/g, "-")}`;
}

function tokenOf(css: string): OverridableToken | null {
  if (css === "--focus") return "accent";
  const token = css.slice(2).replace(/-/g, "_");
  return isOverridableToken(token) ? token : null;
}

/** Jetons du thème après surcharge (valeurs `#rrggbb` seulement) ; le focus suit l'accent. */
export function effectiveTokens(
  theme: ThemeName,
  overrides: TokenOverrides = {},
  palette: ContractPalette = CONTRACT_PALETTE,
): Record<string, string> {
  const tokens: Record<string, string> = { ...palette[theme] };
  for (const token of OVERRIDABLE_TOKENS) {
    const value = normalizeHex(overrides[token]);
    if (value) tokens[cssName(token)] = value;
  }
  const accent = tokens["--accent"];
  if (accent) tokens["--focus"] = accent;
  return tokens;
}

export interface ContrastProblem {
  theme: ThemeName;
  /** Jeton surchargé mis en cause (champ `theme.<thème>.<jeton>` de la requête). */
  token: OverridableToken;
  kind: "contraste" | "statut";
  pair?: TokenPair;
  ratio?: number;
  minimum?: number;
}

/** Problèmes d'un thème (liste vide : conforme). Mêmes règles et même attribution que l'API. */
export function themeProblems(
  theme: ThemeName,
  overrides: TokenOverrides = {},
  palette: ContractPalette = CONTRACT_PALETTE,
): ContrastProblem[] {
  const tokens = effectiveTokens(theme, overrides, palette);
  const problems: ContrastProblem[] = [];
  const groups: [readonly TokenPair[], number][] = [
    [GUARDED_TEXT_PAIRS, TEXT_MINIMUM],
    [GUARDED_UI_PAIRS, UI_MINIMUM],
  ];
  for (const [pairs, minimum] of groups) {
    for (const pair of pairs) {
      const fg = tokens[pair[0]];
      const bg = tokens[pair[1]];
      if (!fg || !bg) continue;
      const ratio = contrastRatio(fg, bg);
      if (ratio >= minimum) continue;
      const touched = [tokenOf(pair[0]), tokenOf(pair[1])].filter((t): t is OverridableToken => t !== null);
      const blamed = touched.filter((t) => overrides[t] !== undefined);
      for (const token of new Set(blamed.length > 0 ? blamed : touched)) {
        problems.push({ theme, token, kind: "contraste", pair, ratio, minimum });
      }
    }
  }
  const accent = tokens["--accent"];
  if (overrides.accent !== undefined && accent && STATUS_TOKENS.some((s) => tokens[s] === accent)) {
    problems.push({ theme, token: "accent", kind: "statut" });
  }
  return problems;
}

/** Problèmes de toute la marque (clair puis sombre). */
export function brandProblems(theme: BrandTheme, palette: ContractPalette = CONTRACT_PALETTE): ContrastProblem[] {
  return THEMES.flatMap((name) => themeProblems(name, theme[name] ?? {}, palette));
}
