import type { MetadataRoute } from "next";
import { t } from "@/i18n";
import { lightToken } from "@/lib/tokens.server";

export const dynamic = "force-static";

/** PWA installable légère : l'espace adhérent sur l'écran d'accueil, la carte d'abord. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: t("app.fullName"),
    short_name: t("app.shortName"),
    description: t("app.description"),
    lang: "fr",
    dir: "ltr",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: lightToken("bg"),
    theme_color: lightToken("surface"),
    categories: ["medical", "finance"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
