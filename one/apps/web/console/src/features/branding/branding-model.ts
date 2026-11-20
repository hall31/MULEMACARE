/**
 * Modèle de l'écran « Marque de l'organisation » (P3), sans React : brouillon du formulaire,
 * requête `updateBrandingSettings`, contraste en direct (même calcul que l'API), couleur conforme la
 * plus proche, variables de l'aperçu, erreurs de l'API rattachées à leur champ.
 */
import {
  CONTRACT_PALETTE,
  GUARDED_TEXT_PAIRS,
  GUARDED_UI_PAIRS,
  OVERRIDABLE_TOKENS,
  TEXT_MINIMUM,
  THEMES,
  UI_MINIMUM,
  contrastRatio,
  effectiveTokens,
  nearestCompliant,
  normalizeHex,
  themeProblems,
  type ContrastProblem,
  type OverridableToken,
  type ThemeName,
  type TokenOverrides,
  type TokenPair,
} from "@shared/brand";
import type { BrandingSettings, BrandLogo, Problem, UpdateBrandingRequest } from "@/api/types";

export { OVERRIDABLE_TOKENS, THEMES, type OverridableToken, type ThemeName };

/** Saisie brute des couleurs : chaîne vide = jeton non surchargé (valeur du contrat). */
export type ColorDraft = Record<ThemeName, Record<OverridableToken, string>>;

export interface BrandingDraft {
  displayName: string;
  logo: BrandLogo | null;
  colors: ColorDraft;
  customDomain: string;
  legalNotice: string;
  privacyNotice: string;
}

const emptyColors = (): Record<OverridableToken, string> => ({ accent: "", accent_hover: "", accent_fg: "", brand_deep: "" });

export function draftFromSettings(settings: BrandingSettings): BrandingDraft {
  const colors: ColorDraft = { light: emptyColors(), dark: emptyColors() };
  for (const theme of THEMES) {
    const overrides = (settings.theme[theme] ?? {}) as TokenOverrides;
    for (const token of OVERRIDABLE_TOKENS) colors[theme][token] = overrides[token] ?? "";
  }
  return {
    displayName: settings.display_name,
    logo: settings.logo,
    colors,
    customDomain: settings.custom_domain ?? "",
    legalNotice: settings.legal_notice ?? "",
    privacyNotice: settings.privacy_notice ?? "",
  };
}

export const colorField = (theme: ThemeName, token: OverridableToken) => `theme.${theme}.${token}`;

/** Surcharges valides d'un thème (les saisies vides ou hors format n'en font pas partie). */
export function overridesOf(draft: BrandingDraft, theme: ThemeName): TokenOverrides {
  const overrides: TokenOverrides = {};
  for (const token of OVERRIDABLE_TOKENS) {
    const value = normalizeHex(draft.colors[theme][token]);
    if (value) overrides[token] = value;
  }
  return overrides;
}

export type DraftErrorKey = "displayName" | "format" | "domain" | "notice";

/** Erreurs de saisie bloquantes (format) ; le contraste, lui, est jugé par l'API. Clé = champ. */
export function draftErrors(draft: BrandingDraft): Record<string, DraftErrorKey> {
  const errors: Record<string, DraftErrorKey> = {};
  const name = draft.displayName.trim();
  if (name.length < 1 || name.length > 80 || /[<>]/.test(name)) errors.display_name = "displayName";
  for (const theme of THEMES) {
    for (const token of OVERRIDABLE_TOKENS) {
      const raw = draft.colors[theme][token].trim();
      if (raw && !normalizeHex(raw)) errors[colorField(theme, token)] = "format";
    }
  }
  const domain = draft.customDomain.trim();
  if (domain && !/^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(domain)) errors.custom_domain = "domain";
  if (draft.legalNotice.length > 4000 || /[<>]/.test(draft.legalNotice)) errors.legal_notice = "notice";
  if (draft.privacyNotice.length > 4000 || /[<>]/.test(draft.privacyNotice)) errors.privacy_notice = "notice";
  return errors;
}

export function requestFromDraft(draft: BrandingDraft): UpdateBrandingRequest {
  const theme: UpdateBrandingRequest["theme"] = {};
  for (const name of THEMES) {
    const overrides = overridesOf(draft, name);
    if (Object.keys(overrides).length > 0) theme[name] = overrides;
  }
  const text = (value: string) => (value.trim() ? value.trim() : null);
  return {
    display_name: draft.displayName.trim(),
    logo: draft.logo,
    theme,
    custom_domain: text(draft.customDomain),
    legal_notice: text(draft.legalNotice),
    privacy_notice: text(draft.privacyNotice),
  };
}

export interface PairCheck {
  pair: TokenPair;
  ratio: number;
  minimum: number;
  ok: boolean;
}

/** Contraste en direct d'un thème : chaque paire gardée par le contrat, et les problèmes. */
export function contrastReport(draft: BrandingDraft, theme: ThemeName): { pairs: PairCheck[]; problems: ContrastProblem[] } {
  const overrides = overridesOf(draft, theme);
  const tokens = effectiveTokens(theme, overrides);
  const pairs: PairCheck[] = [];
  for (const [list, minimum] of [
    [GUARDED_TEXT_PAIRS, TEXT_MINIMUM],
    [GUARDED_UI_PAIRS, UI_MINIMUM],
  ] as const) {
    for (const pair of list) {
      const fg = tokens[pair[0]];
      const bg = tokens[pair[1]];
      if (!fg || !bg) continue;
      const ratio = contrastRatio(fg, bg);
      pairs.push({ pair, ratio, minimum, ok: ratio >= minimum });
    }
  }
  return { pairs, problems: themeProblems(theme, overrides) };
}

/** Couleur conforme la plus proche pour un jeton saisi (null : rien à proposer ou déjà conforme). */
export function suggestionFor(draft: BrandingDraft, theme: ThemeName, token: OverridableToken): string | null {
  const value = normalizeHex(draft.colors[theme][token]);
  if (!value) return null;
  const others = { ...overridesOf(draft, theme) };
  delete others[token];
  const nearest = nearestCompliant(theme, token, value, others);
  return nearest && nearest !== value ? nearest : null;
}

/** Valeur effective d'un jeton (saisie valide, sinon valeur du contrat) : pour le sélecteur de couleur. */
export function effectiveColor(draft: BrandingDraft, theme: ThemeName, token: OverridableToken): string {
  return normalizeHex(draft.colors[theme][token]) ?? CONTRACT_PALETTE[theme][`--${token.replace(/_/g, "-")}`] ?? "";
}

/** Variables CSS de l'aperçu d'un thème : toutes les couleurs du contrat, surcharges comprises. */
export function previewVariables(draft: BrandingDraft, theme: ThemeName): Record<string, string> {
  return effectiveTokens(theme, overridesOf(draft, theme));
}

/** Erreurs de l'API par champ (`theme.light.accent`, `logo`, `custom_domain`…). */
export function problemFieldErrors(problem: Problem | null | undefined): Record<string, string[]> {
  const byField: Record<string, string[]> = {};
  for (const error of problem?.errors ?? []) (byField[error.field] ??= []).push(error.message);
  if (problem?.code === "BRD-03" && !byField.logo) byField.logo = [problem.message];
  if (problem?.code === "BRD-04" && !byField.custom_domain) byField.custom_domain = [problem.message];
  return byField;
}

export const LOGO_MAX_BYTES = 32 * 1024;
const LOGO_TYPES = ["image/png", "image/webp", "image/jpeg", "image/svg+xml"];

export type LogoRead = { ok: true; logo: BrandLogo } | { ok: false; reason: "type" | "size" | "read" };

/** Fichier choisi → data-URI (l'API revérifie la signature et assainit le SVG, BRD-03). */
export async function readLogoFile(file: File): Promise<LogoRead> {
  if (!LOGO_TYPES.includes(file.type)) return { ok: false, reason: "type" };
  if (file.size > LOGO_MAX_BYTES) return { ok: false, reason: "size" };
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    return { ok: true, logo: { kind: "data_uri", src: `data:${file.type};base64,${btoa(binary)}` } };
  } catch {
    return { ok: false, reason: "read" };
  }
}
