import { cookies, headers } from "next/headers";
import { cache } from "react";
import { BRAND_FIXTURE_COOKIE, describeFallback, loadBrand, type ResolvedBrand } from "@shared/brand";

/**
 * Marque de l'organisation (P3), lue au rendu serveur, avant le premier affichage : aucun flash du
 * thème MulemaCare puis de la marque. Tests et démonstration (`MULEMA_BRANDING_FIXTURES=enabled`) :
 * organisations fictives choisies par le cookie `mc-org`. Sinon : `MULEMA_ORGANIZATION_SLUG`
 * (déploiement dédié) ou domaine personnalisé (en-tête Host), lus sur l'API relayée
 * (`getOrganizationBranding`, sans jeton, 800 ms au plus, cache 5 min). Hors ligne, la page servie
 * par le service worker garde la marque de son dernier rendu.
 */
const FIXTURES = process.env.MULEMA_BRANDING_FIXTURES === "enabled";
const API_URL = process.env.MULEMA_API_URL ?? "http://localhost:4010";

export const getBrand = cache(async (): Promise<ResolvedBrand> => {
  const envSlug = process.env.MULEMA_ORGANIZATION_SLUG ?? null;
  const cookieSlug = FIXTURES ? ((await cookies()).get(BRAND_FIXTURE_COOKIE)?.value ?? null) : null;
  const host = FIXTURES || envSlug ? null : (await headers()).get("host");
  const brand = await loadBrand({ fixtures: FIXTURES, cookieSlug, envSlug, host, apiUrl: API_URL, fetchOptions: { init: { next: { revalidate: 300 } } } });
  const warning = process.env.NODE_ENV === "production" ? null : describeFallback(brand);
  if (warning) console.warn(warning);
  return brand;
});
