/** Moteur de thème par organisation (P3, marque blanche) : point d'entrée unique des apps. */
export { HEX_COLOR, contrastRatio, normalizeHex, relativeLuminance } from "./contrast";
export { CONTRACT_PALETTE } from "./contract-palette";
export { brandPreviewVariables, brandStyleSheet } from "./css";
export { BRANDING_FIXTURES, BRAND_FIXTURE_COOKIE, BRAND_FIXTURE_SLUGS, type BrandingFixture } from "./fixtures";
export { MAX_LOGO_SRC_LENGTH, safeLogoSrc } from "./logo";
export { nearestCompliant } from "./nearest";
export {
  GUARDED_TEXT_PAIRS,
  GUARDED_UI_PAIRS,
  OVERRIDABLE_TOKENS,
  TEXT_MINIMUM,
  THEMES,
  UI_MINIMUM,
  brandProblems,
  cssName,
  effectiveTokens,
  isOverridableToken,
  themeProblems,
  type BrandTheme,
  type ContrastProblem,
  type OverridableToken,
  type TokenOverrides,
  type TokenPair,
} from "./policy";
export { DEFAULT_BRAND, parseBrandTheme, resolveBrand, type BrandFallback, type BrandFallbackReason, type BrandIdentity, type BrandLoad, type ResolvedBrand } from "./resolve";
export { brandQuery, domainFromHost, fetchBranding, fixtureBranding, type BrandQuery } from "./source";
export type { ContractPalette, ThemeName } from "./tokens";
export { describeFallback, loadBrand, type BrandRequest } from "./load";
