import { NextResponse, type NextRequest } from "next/server";
import { NO_STORE, contentSecurityPolicy, generateNonce, logoOrigins } from "@shared/security/headers";

/**
 * CSP stricte par requête (phase 4, voie 2, `@shared/security/headers`) : nonce neuf à chaque
 * document, transmis à Next.js par l'en-tête de la REQUÊTE (il le pose sur ses scripts) et au
 * `<style>` de la marque (`x-nonce`, lu par `BrandStyle`). Un `x-nonce` envoyé par le client est
 * écrasé. Espace adhérent et page de paiement : jamais en cache HTTP (`Cache-Control: no-store`).
 * Les en-têtes communs à toutes les réponses sont dans `next.config.ts`.
 */
export function proxy(request: NextRequest): NextResponse {
  const nonce = generateNonce();
  const csp = contentSecurityPolicy({
    nonce,
    dev: process.env.NODE_ENV === "development",
    images: logoOrigins(process.env.MULEMA_LOGO_HOSTS),
  });
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Cache-Control", NO_STORE);
  return response;
}

// Littéral exigé par Next (analyse statique) ; identique à PROXY_EXCLUDED, vérifié par
// apps/web/shared/security/headers.test.ts. Préchargements exclus (pas de document rendu).
export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico|icons/|sw.js|mockServiceWorker.js|manifest.webmanifest).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
