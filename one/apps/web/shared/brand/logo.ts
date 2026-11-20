/**
 * Logo de marque : l'API l'a déjà assaini (BRD-03 : chemin interne, `https` vers un hôte de la liste
 * blanche, data-URI PNG/WebP/JPEG à signature vérifiée ou SVG assaini, 32 Ko). Défense en
 * profondeur côté client : on ne garde que ces trois formes, et l'interface ne l'affiche que dans
 * un `<img>` (un SVG chargé en image n'exécute jamais de script ni de requête). Tout le reste → null.
 */
export interface BrandLogoInput {
  kind: "url" | "data_uri";
  src: string;
}

/** Longueur maximale du contrat (`BrandLogo.src`). */
export const MAX_LOGO_SRC_LENGTH = 43_756;

const DATA_URI = /^data:image\/(?:png|webp|jpeg|svg\+xml);base64,[A-Za-z0-9+/]+={0,2}$/;
const INTERNAL_PATH = /^\/[A-Za-z0-9._~/-]{1,512}$/;
const URL_PATH = /^\/[A-Za-z0-9._~/-]{0,512}$/;

export function safeLogoSrc(logo: unknown): string | null {
  if (typeof logo !== "object" || logo === null) return null;
  const { kind, src } = logo as Partial<BrandLogoInput>;
  if (typeof src !== "string" || src.length === 0 || src.length > MAX_LOGO_SRC_LENGTH) return null;
  if (kind === "data_uri") return DATA_URI.test(src) ? src : null;
  if (kind !== "url") return null;
  if (src.startsWith("/")) {
    return INTERNAL_PATH.test(src) && !src.includes("..") && !src.includes("//") ? src : null;
  }
  let url: URL;
  try {
    url = new URL(src);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash) return null;
  if (!URL_PATH.test(url.pathname) || url.pathname.includes("..") || url.pathname.includes("//")) return null;
  return url.href;
}
