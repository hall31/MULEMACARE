/**
 * Trois organisations FICTIVES de test pour la marque blanche (réponses de `getOrganizationBranding`,
 * validées contre specs/openapi.yaml par les tests de contrat des apps). Données de démonstration,
 * pas du code d'interface : les couleurs ne sont jamais appliquées sans passer par `resolveBrand`.
 *
 * - `lagune-sante` (CI) : prune, logo SVG ; conforme AA en clair et en sombre.
 * - `teranga-assurances` (SN) : bleu pétrole, logo SVG ; conforme.
 * - `marque-agressive` (CI) : jaune vif en clair (1,43:1 sur la surface) : l'API l'aurait refusée
 *   (BRD-01) ; si elle arrivait quand même, le client DOIT la replier sur le thème MulemaCare.
 */
export interface BrandingFixture {
  slug: string;
  display_name: string;
  country_code: "CI" | "SN";
  currency: "XOF";
  logo: { kind: "url" | "data_uri"; src: string } | null;
  theme: Record<string, Record<string, string>>;
  custom_domain: string | null;
  legal_notice: string | null;
  privacy_notice: string | null;
}

/** Cookie de choix de l'organisation de démonstration (lu seulement en mode démonstration ou test). */
export const BRAND_FIXTURE_COOKIE = "mc-org";

const LAGUNE_LOGO =
  "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHRpdGxlPkxhZ3VuZTwvdGl0bGU+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMiIgcj0iMzAiIGZpbGw9IiM2ZDJlOGMiLz48cGF0aCBkPSJNMTAgMzhjNi02IDEyLTYgMTggMHMxMiA2IDE4IDAgOC01IDgtNXY4Yy00IDQtMTAgNi0xNiAycy0xMi02LTE4IDAtMTAgMi0xMCAyeiIgZmlsbD0iI2ZmZmZmZiIvPjxjaXJjbGUgY3g9IjQwIiBjeT0iMjIiIHI9IjciIGZpbGw9IiNmMmM5NGMiLz48L3N2Zz4=";
const TERANGA_LOGO =
  "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCI+PHRpdGxlPlRlcmFuZ2E8L3RpdGxlPjxyZWN0IHdpZHRoPSI2NCIgaGVpZ2h0PSI2NCIgcng9IjE0IiBmaWxsPSIjMGI1ZjhhIi8+PHBhdGggZD0iTTE0IDQ0aDM2djZIMTR6IiBmaWxsPSIjZmZmZmZmIi8+PGNpcmNsZSBjeD0iMzIiIGN5PSIzMCIgcj0iMTEiIGZpbGw9IiNmZmZmZmYiLz48Y2lyY2xlIGN4PSIzMiIgY3k9IjMwIiByPSI1IiBmaWxsPSIjMGI1ZjhhIi8+PC9zdmc+";

export const BRANDING_FIXTURES: Readonly<Record<string, BrandingFixture>> = {
  "lagune-sante": {
    slug: "lagune-sante",
    display_name: "Mutuelle Lagune Santé",
    country_code: "CI",
    currency: "XOF",
    logo: { kind: "data_uri", src: LAGUNE_LOGO },
    theme: {
      light: { accent: "#6d2e8c", accent_hover: "#5a2474", accent_fg: "#ffffff", brand_deep: "#3f1a52" },
      dark: { accent: "#d4a8ea", accent_hover: "#e3c4f2", brand_deep: "#3a1f4a" },
    },
    custom_domain: "sante.lagune.invalid",
    legal_notice: "Mutuelle Lagune Santé, mutuelle fictive de démonstration.",
    privacy_notice: null,
  },
  "teranga-assurances": {
    slug: "teranga-assurances",
    display_name: "Teranga Assurances",
    country_code: "SN",
    currency: "XOF",
    logo: { kind: "data_uri", src: TERANGA_LOGO },
    theme: {
      light: { accent: "#0b5f8a", accent_hover: "#084a6c", brand_deep: "#08364f" },
      dark: { accent: "#7cc4e8", accent_hover: "#a3d7f1", brand_deep: "#0b3550" },
    },
    custom_domain: null,
    legal_notice: null,
    privacy_notice: null,
  },
  "marque-agressive": {
    slug: "marque-agressive",
    display_name: "Marque Agressive (test)",
    country_code: "CI",
    currency: "XOF",
    logo: null,
    theme: {
      light: { accent: "#ffd400", accent_hover: "#ffe14d", accent_fg: "#ffffff" },
      dark: { accent: "#ffd400" },
    },
    custom_domain: null,
    legal_notice: null,
    privacy_notice: null,
  },
};

export const BRAND_FIXTURE_SLUGS = Object.keys(BRANDING_FIXTURES);
