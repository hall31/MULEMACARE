import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const here = path.dirname(fileURLToPath(import.meta.url));

/**
 * L'API est servie sous le même origine (`/api/*`) et relayée vers MULEMA_API_URL :
 * pas de CORS, et le service worker peut exclure toutes les réponses d'API de son cache.
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
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
