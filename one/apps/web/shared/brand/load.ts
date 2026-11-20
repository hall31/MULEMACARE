/**
 * Point d'entrée des layouts (rendu serveur) : quelle organisation, d'où lire sa marque, ce qu'on
 * applique. Les apps ne lisent que l'environnement, le cookie de démonstration et l'en-tête Host.
 */
import { resolveBrand, type ResolvedBrand } from "./resolve";
import { brandQuery, fetchBranding, fixtureBranding, type FetchBrandingOptions } from "./source";

export interface BrandRequest {
  /** Démonstration ou test : organisations fictives, cookie `mc-org` lu, aucun réseau. */
  fixtures: boolean;
  cookieSlug?: string | null;
  envSlug?: string | null;
  host?: string | null;
  apiUrl: string;
  fetchOptions?: FetchBrandingOptions;
}

export async function loadBrand(request: BrandRequest): Promise<ResolvedBrand> {
  const query = brandQuery(request);
  const load = request.fixtures ? fixtureBranding(query) : await fetchBranding(request.apiUrl, query, request.fetchOptions);
  return resolveBrand(load);
}

/** Ligne de console (développement seulement) qui dit pourquoi la marque est repliée. */
export function describeFallback(brand: ResolvedBrand): string | null {
  if (!brand.fallback) return null;
  const who = brand.identity ? ` (${brand.identity.slug})` : "";
  return `[marque blanche] repli sur le thème MulemaCare${who} : ${brand.fallback.reason}${brand.fallback.details.length ? ` — ${brand.fallback.details.join(" ; ")}` : ""}`;
}
