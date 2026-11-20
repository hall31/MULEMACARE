/**
 * D'où vient la marque, et sa lecture avant le premier rendu (rendu serveur des layouts).
 *
 * Organisation demandée, dans l'ordre :
 * 1. démonstration ou test seulement : cookie `mc-org` (une des organisations fictives) ;
 * 2. déploiement dédié : `MULEMA_ORGANIZATION_SLUG` ;
 * 3. domaine personnalisé : l'hôte de la requête (ni `localhost`, ni adresse IP, ni nom sans point).
 * Aucune : thème MulemaCare, aucun appel.
 *
 * Lecture : `GET /v1/public/branding?slug=…|domain=…` (sans jeton), délai borné ; 404, réponse non
 * JSON, coupure ou délai dépassé → repli (jamais d'erreur visible, jamais d'attente du rendu au-delà
 * du délai). En démonstration, les organisations fictives sont servies sans réseau.
 */
import { BRANDING_FIXTURES } from "./fixtures";
import type { BrandLoad } from "./resolve";

export type BrandQuery = { slug: string } | { domain: string };

const SLUG = /^[a-z0-9][a-z0-9-]{1,62}$/;
const DOMAIN = /^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;

/** Domaine personnalisé tiré de l'en-tête Host, ou null (local, IP, forme invalide). */
export function domainFromHost(host: string | null | undefined): string | null {
  if (!host) return null;
  const name = host.trim().toLowerCase().replace(/:\d+$/, "");
  if (name.length < 4 || name.length > 253 || name === "localhost" || name.endsWith(".localhost")) return null;
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(name) || name.startsWith("[")) return null;
  return DOMAIN.test(name) ? name : null;
}

export function brandQuery(input: {
  fixtures: boolean;
  cookieSlug?: string | null;
  envSlug?: string | null;
  host?: string | null;
}): BrandQuery | null {
  if (input.fixtures && input.cookieSlug && SLUG.test(input.cookieSlug)) return { slug: input.cookieSlug };
  if (input.envSlug && SLUG.test(input.envSlug)) return { slug: input.envSlug };
  const domain = domainFromHost(input.host);
  return domain ? { domain } : null;
}

/** Organisations fictives (démonstration et tests) : jamais de réseau. */
export function fixtureBranding(query: BrandQuery | null): BrandLoad {
  if (!query || !("slug" in query)) return { status: "absent" };
  const fixture = BRANDING_FIXTURES[query.slug];
  return fixture ? { status: "ok", payload: structuredClone(fixture) } : { status: "absent" };
}

export interface FetchBrandingOptions {
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  /** Options supplémentaires (par exemple `next: { revalidate }` côté Next.js). */
  init?: RequestInit & Record<string, unknown>;
}

export async function fetchBranding(apiUrl: string, query: BrandQuery | null, options: FetchBrandingOptions = {}): Promise<BrandLoad> {
  if (!query) return { status: "absent" };
  const { fetchImpl = fetch, timeoutMs = 800, init = {} } = options;
  let url: URL;
  try {
    url = new URL(`${apiUrl.replace(/\/$/, "")}/v1/public/branding`);
  } catch {
    return { status: "erreur", detail: "adresse de l'API invalide" };
  }
  if ("slug" in query) url.searchParams.set("slug", query.slug);
  else url.searchParams.set("domain", query.domain);
  try {
    const response = await fetchImpl(url, {
      ...init,
      method: "GET",
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (response.status === 404) return { status: "absent" };
    if (!response.ok) return { status: "erreur", detail: `HTTP ${response.status}` };
    return { status: "ok", payload: (await response.json()) as unknown };
  } catch (error) {
    return { status: "erreur", detail: error instanceof Error ? error.name : "réseau" };
  }
}
