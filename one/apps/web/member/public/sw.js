/*
 * Service worker de l'espace adhérent MulemaCare (PWA légère).
 * - Met en cache la coquille (pages, scripts, polices, icônes) pour rouvrir l'espace sans réseau :
 *   la carte s'affiche alors depuis la dernière lecture (sans QR, gardée par la page).
 * - Ne met JAMAIS en cache une réponse d'API (/api/*) : le QR et les données restent hors du
 *   cache HTTP.
 * - Ne met jamais en cache la page publique de paiement (/payer/*) : le jeton est dans l'adresse.
 * - Aucune requête vers un autre domaine n'est interceptée.
 */
const VERSION = "adherent-v1";
const SHELL = ["/", "/soins", "/cotisations", "/famille", "/notifications", "/decouverte", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(VERSION)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

function isStaticAsset(url) {
  return url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/");
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(VERSION);
    await cache.put(request, response.clone());
  }
  return response;
}

/** Réseau d'abord ; hors ligne, la même page en cache, sinon la carte (« / »). */
async function networkFirstPage(request, url) {
  const cache = await caches.open(VERSION);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(url.pathname, response.clone());
    return response;
  } catch {
    const cached = (await cache.match(url.pathname)) || (await cache.match("/"));
    if (cached) return cached;
    throw new Error("hors ligne et coquille absente du cache");
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/payer/")) return;
  if (request.mode === "navigate") {
    event.respondWith(networkFirstPage(request, url));
    return;
  }
  if (isStaticAsset(url) || url.pathname === "/manifest.webmanifest") {
    event.respondWith(cacheFirst(request));
  }
});
