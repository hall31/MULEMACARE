import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";
import { staticSecurityHeaders } from "../shared/security/headers";

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * L'API est servie sous la même origine (`/api/*`) et relayée vers MULEMA_API_URL :
 * pas de CORS, et le service worker exclut toutes les réponses d'API de son cache.
 * Par défaut : le serveur de mocks Prism (`make mock-api`, port 4010).
 */
const apiUrl = process.env.MULEMA_API_URL ?? "http://localhost:4010";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Les jetons de design sont lus directement dans specs/design (source unique, pas de copie).
  turbopack: { root: path.join(here, "../../..") },
  outputFileTracingRoot: path.join(here, "../../.."),
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
      {
        // En-têtes communs (phase 4, voie 2) : HSTS en production, nosniff, no-referrer (jetons dans
        // le chemin), DENY, COOP, Permissions-Policy. CSP à nonce : src/proxy.ts.
        source: "/:path*",
        headers: staticSecurityHeaders("member", { production: process.env.NODE_ENV === "production" }),
      },
      {
        // Page publique du payeur : jamais indexée (le jeton donne accès au paiement).
        source: "/payer/:token*",
        headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
      },
    ];
  },
};

export default nextConfig;
