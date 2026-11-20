/**
 * Moteur de thème par organisation : de la réponse de `getOrganizationBranding` (non fiable : elle
 * vient du réseau) à ce que l'interface applique. Trois sorties seulement :
 * - l'identité (nom affiché en texte brut, logo assaini, slug) ;
 * - la feuille de style de la LISTE FERMÉE de jetons ;
 * - le repli, et pourquoi (absente, invalide, contraste, erreur).
 *
 * Repli sûr : sans marque, marque illisible ou en erreur → thème MulemaCare (aucun jeton surchargé).
 * Garde de contraste en défense en profondeur : si une paire dérivée échoue AA dans un thème, TOUTE
 * la marque de couleurs est écartée (clair et sombre : une marque à moitié appliquée n'est plus la
 * marque) ; le nom et le logo, eux, restent s'ils sont valides.
 */
import { normalizeHex } from "./contrast";
import { CONTRACT_PALETTE } from "./contract-palette";
import { brandStyleSheet } from "./css";
import { safeLogoSrc } from "./logo";
import { OVERRIDABLE_TOKENS, THEMES, brandProblems, type BrandTheme, type ContrastProblem, type TokenOverrides } from "./policy";
import type { ContractPalette } from "./tokens";

export type BrandLoad = { status: "absent" } | { status: "erreur"; detail: string } | { status: "ok"; payload: unknown };

export interface BrandIdentity {
  slug: string;
  /** Texte brut : toujours rendu échappé (nœud texte React), jamais en HTML. */
  displayName: string;
  /** Source sûre pour un `<img>`, ou null. */
  logoSrc: string | null;
  countryCode: "CI" | "SN";
}

export type BrandFallbackReason = "absente" | "invalide" | "contraste" | "erreur";

export interface BrandFallback {
  reason: BrandFallbackReason;
  details: string[];
}

export interface ResolvedBrand {
  identity: BrandIdentity | null;
  /** Thème retenu (null : thème MulemaCare). */
  theme: BrandTheme | null;
  /** CSS à injecter avant le premier rendu (chaîne vide : rien). */
  css: string;
  fallback: BrandFallback | null;
}

const SLUG = /^[a-z0-9][a-z0-9-]{1,62}$/;
const MAX_DISPLAY_NAME = 120;

export const DEFAULT_BRAND: ResolvedBrand = { identity: null, theme: null, css: "", fallback: null };

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

/** Thème de la LISTE FERMÉE, ou la liste des écarts (clé inconnue, thème inconnu, couleur hors format). */
export function parseBrandTheme(raw: unknown): { theme: BrandTheme } | { errors: string[] } {
  if (raw === undefined || raw === null) return { theme: {} };
  if (!isRecord(raw)) return { errors: ["theme"] };
  const errors: string[] = [];
  const theme: BrandTheme = {};
  for (const [name, value] of Object.entries(raw)) {
    if (!(THEMES as readonly string[]).includes(name)) {
      errors.push(`theme.${name}`);
      continue;
    }
    if (!isRecord(value)) {
      errors.push(`theme.${name}`);
      continue;
    }
    const overrides: TokenOverrides = {};
    for (const [token, color] of Object.entries(value)) {
      const hex = normalizeHex(color);
      if (!(OVERRIDABLE_TOKENS as readonly string[]).includes(token) || !hex) {
        errors.push(`theme.${name}.${token}`);
        continue;
      }
      overrides[token as keyof TokenOverrides] = hex;
    }
    theme[name as keyof BrandTheme] = overrides;
  }
  return errors.length > 0 ? { errors } : { theme };
}

function parseIdentity(payload: Record<string, unknown>): BrandIdentity | null {
  const { slug, display_name: name, country_code: country, currency } = payload;
  if (typeof slug !== "string" || !SLUG.test(slug)) return null;
  if (typeof name !== "string") return null;
  // Texte brut seulement : caractères de contrôle retirés, longueur bornée.
  const displayName = name.replace(/[\u0000-\u001f\u007f]/g, "").trim().slice(0, MAX_DISPLAY_NAME);
  if (!displayName) return null;
  if (country !== "CI" && country !== "SN") return null;
  if (currency !== "XOF") return null;
  return { slug, displayName, logoSrc: safeLogoSrc(payload.logo), countryCode: country };
}

const describe = (p: ContrastProblem) =>
  p.kind === "statut"
    ? `${p.theme}.${p.token}: accent = couleur de statut`
    : `${p.theme}.${p.token}: ${p.pair?.[0]} / ${p.pair?.[1]} = ${(p.ratio ?? 0).toFixed(2)}:1 < ${p.minimum}:1`;

export function resolveBrand(load: BrandLoad, palette: ContractPalette = CONTRACT_PALETTE): ResolvedBrand {
  if (load.status === "absent") return DEFAULT_BRAND;
  if (load.status === "erreur") return { ...DEFAULT_BRAND, fallback: { reason: "erreur", details: [load.detail] } };
  const payload = load.payload;
  const identity = isRecord(payload) ? parseIdentity(payload) : null;
  if (!identity || !isRecord(payload)) return { ...DEFAULT_BRAND, fallback: { reason: "invalide", details: ["réponse hors contrat"] } };

  const parsed = parseBrandTheme(payload.theme);
  if ("errors" in parsed) return { identity, theme: null, css: "", fallback: { reason: "invalide", details: parsed.errors } };

  const problems = brandProblems(parsed.theme, palette);
  if (problems.length > 0) return { identity, theme: null, css: "", fallback: { reason: "contraste", details: problems.map(describe) } };

  const css = brandStyleSheet(parsed.theme);
  return { identity, theme: css ? parsed.theme : null, css, fallback: null };
}
