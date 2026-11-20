import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";
import { staticSecurityHeaders } from "../shared/security/headers";

const here = path.dirname(fileURLToPath(import.meta.url));
// Racine de MulemaCare One : la console importe les jetons de specs/design sans les copier.
const productRoot = path.resolve(here, "../../..");

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  turbopack: { root: productRoot },
  outputFileTracingRoot: productRoot,
  async headers() {
    return [
      {
        // En-têtes communs (phase 4, voie 2) : HSTS en production, nosniff, no-referrer (jetons dans
        // le chemin), DENY, COOP, Permissions-Policy. CSP à nonce : src/proxy.ts.
        source: "/:path*",
        headers: staticSecurityHeaders("console", { production: process.env.NODE_ENV === "production" }),
      },
    ];
  },
};

export default config;
