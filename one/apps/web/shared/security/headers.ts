/**
 * En-têtes de sécurité des apps web (phase 4, voie 2) : une seule source pour la console, le
 * comptoir, l'espace adhérent et les espaces partenaires.
 *
 * - CSP stricte par requête (`proxy.ts` de chaque app) : scripts et feuilles de style autorisés par
 *   NONCE seulement (Next.js l'applique à ses scripts ; le `<style id="mc-brand">` de la marque le
 *   porte explicitement), `'strict-dynamic'`, aucun `'unsafe-inline'` ni `'unsafe-eval'` en
 *   production. Seule exception : `style-src-attr 'unsafe-inline'` (attributs `style=""` rendus par
 *   React côté serveur pour des largeurs de barres ; aucun script, aucun sélecteur).
 * - En-têtes statiques (`next.config.ts`) : HSTS (production), nosniff, Referrer-Policy no-referrer
 *   (les jetons de paiement sont dans le chemin), X-Frame-Options DENY, COOP, Permissions-Policy
 *   propre à chaque app (seul le comptoir a la caméra, pour scanner le QR).
 *
 * Aucune dépendance : chaîne de caractères pure, testée par `headers.test.ts`.
 */

export type AppKind = "console" | "counter" | "member" | "partner";

export interface Header {
  key: string;
  value: string;
}

export interface CspInput {
  nonce: string;
  /** `next dev` : React exige `'unsafe-eval'`, le rechargement à chaud un WebSocket. */
  dev: boolean;
  /** Origines supplémentaires pour `fetch` (API servie sur une autre origine). */
  connect?: readonly string[];
  /** Origines supplémentaires pour les images (hôtes de logos autorisés, en https). */
  images?: readonly string[];
}

const NONCE = /^[A-Za-z0-9+/]{16,}={0,2}$/;

/** Nonce de 128 bits, base64, imprévisible (Web Crypto, disponible dans le runtime du proxy). */
export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

/** Origine `http(s)://hôte[:port]` d'une URL, ou `null` (jamais de chemin ni de joker). */
export function originOf(url: string | undefined | null): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null;
    if (parsed.username || parsed.password) return null;
    return parsed.origin;
  } catch {
    return null;
  }
}

const HOST = /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;

/** `MULEMA_LOGO_HOSTS` (« logos.exemple.ci,cdn.exemple.sn ») → origines https ; le reste est ignoré. */
export function logoOrigins(list: string | undefined | null): string[] {
  if (!list) return [];
  return list
    .split(",")
    .map((host) => host.trim().toLowerCase())
    .filter((host) => HOST.test(host))
    .map((host) => `https://${host}`);
}

function sources(...groups: readonly (readonly string[])[]): string {
  return [...new Set(groups.flat())].join(" ");
}

/** Politique de sécurité du contenu d'une réponse HTML. */
export function contentSecurityPolicy(input: CspInput): string {
  if (!NONCE.test(input.nonce)) throw new Error("nonce CSP invalide");
  const nonce = `'nonce-${input.nonce}'`;
  const connect = (input.connect ?? []).filter((o) => originOf(o) === o);
  const images = (input.images ?? []).filter((o) => originOf(o) === o && o.startsWith("https://"));
  const directives: [string, string][] = [
    ["default-src", "'self'"],
    ["script-src", sources(["'self'", nonce, "'strict-dynamic'"], input.dev ? ["'unsafe-eval'"] : [])],
    // En développement, Next injecte les feuilles du rechargement à chaud sans nonce.
    ["style-src", input.dev ? "'self' 'unsafe-inline'" : sources(["'self'", nonce])],
    ["style-src-attr", "'unsafe-inline'"],
    ["img-src", sources(["'self'", "data:", "blob:"], images)],
    ["font-src", "'self'"],
    ["connect-src", sources(["'self'"], connect, input.dev ? ["ws:", "wss:"] : [])],
    ["worker-src", "'self'"],
    ["manifest-src", "'self'"],
    ["media-src", "'self'"],
    ["object-src", "'none'"],
    ["frame-src", "'none'"],
    ["frame-ancestors", "'none'"],
    ["base-uri", "'none'"],
    ["form-action", "'self'"],
  ];
  return directives.map(([name, value]) => `${name} ${value}`).join("; ");
}

/** Une directive d'une CSP sérialisée (tests et contrôle des réponses servies). */
export function cspDirective(csp: string, name: string): string[] | null {
  for (const part of csp.split(";")) {
    const [directive, ...values] = part.trim().split(/\s+/);
    if (directive === name) return values;
  }
  return null;
}

export const PERMISSIONS_POLICY: Record<AppKind, string> = {
  console: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()",
  // Le comptoir scanne le QR de la carte avec la caméra de l'appareil.
  counter: "camera=(self), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()",
  member:
    "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=(), fullscreen=(self), clipboard-write=(self), web-share=(self)",
  partner: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()",
};

/** Deux ans, sous-domaines compris ; pas de `preload` (domaines de marque blanche à valider). */
export const HSTS = "max-age=63072000; includeSubDomains";

/** Pages d'espace adhérent et de paiement : jamais en cache HTTP (partagé ou navigateur). */
export const NO_STORE = "no-store, max-age=0";

/** En-têtes posés sur TOUTES les réponses (pages, scripts, images) par `next.config.ts`. */
export function staticSecurityHeaders(app: AppKind, options: { production: boolean }): Header[] {
  const headers: Header[] = [
    { key: "X-Content-Type-Options", value: "nosniff" },
    // Les jetons (lien de paiement) sont dans le chemin : ils ne partent jamais en Referer.
    { key: "Referrer-Policy", value: "no-referrer" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    { key: "Permissions-Policy", value: PERMISSIONS_POLICY[app] },
  ];
  if (options.production) headers.push({ key: "Strict-Transport-Security", value: HSTS });
  return headers;
}

/**
 * Chemins servis sans proxy (fichiers statiques, API relayée, préchargements) : la CSP ne
 * s'applique qu'aux documents HTML. À recopier tel quel dans `config.matcher` (Next exige un
 * littéral analysable statiquement).
 */
export const PROXY_EXCLUDED =
  "api|_next/static|_next/image|favicon.ico|icons/|sw.js|mockServiceWorker.js|manifest.webmanifest";
