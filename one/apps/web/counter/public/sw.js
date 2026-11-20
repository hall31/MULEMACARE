/*
 * Service worker du comptoir MulemaCare (lot L7).
 * - Met en cache l'application (coquille, scripts, polices, icônes) pour démarrer sans réseau.
 * - Ne met JAMAIS en cache une réponse d'API (/api/*) : données personnelles et décisions
 *   restent hors du cache HTTP. Les accords provisoires vivent dans IndexedDB, côté page.
 * - Aucune requête vers un autre domaine n'est interceptée.
 */
const VERSION = "comptoir-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

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

async function networkFirstPage(request) {
  const cache = await caches.open(VERSION);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put("/", response.clone());
    return response;
  } catch {
    const cached = await cache.match("/");
    if (cached) return cached;
    throw new Error("hors ligne et coquille absente du cache");
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;
  if (request.mode === "navigate") {
    event.respondWith(networkFirstPage(request));
    return;
  }
  if (isStaticAsset(url) || url.pathname === "/manifest.webmanifest") {
    event.respondWith(cacheFirst(request));
  }
});
