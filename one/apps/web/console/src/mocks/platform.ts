/**
 * Mocks P3 de la console (CR-P3-01), mêmes gardes que l'API : marque blanche (liste fermée BRD-02,
 * contraste AA BRD-01 calculé par le même module que le client, logo BRD-03, domaine pris BRD-04)
 * et accueil d'organisation (identifiant pris ORG-01, gabarit inconnu ou d'un autre pays ORG-02).
 * Données FICTIVES ; réponses validées contre specs/openapi.yaml (tests/unit/contract.test.ts).
 */
import { OVERRIDABLE_TOKENS, THEMES, brandProblems, normalizeHex, parseBrandTheme, safeLogoSrc, type BrandTheme } from "@shared/brand";
import type { BrandingSettings, ConfigurationTemplate, FieldError, OrganizationOnboarding } from "@/api/types";

export const TAKEN_DOMAIN = "sante.deja-pris.ci";
/** Démonstration du port DNS (CR-P3-02) : un domaine commençant par « attente. » n'a pas publié son TXT. */
export const UNPROVEN_DOMAIN_PREFIX = "attente.";
/** Domaines réservés (BRD-05) : usage spécial, plateforme, hôtes de l'instance et leurs zones parentes. */
const RESERVED_SUFFIXES = ["localhost", "invalid", "local", "internal", "test", "example", "mulemacare.com", "mulemacare.ci", "mulemacare.invalid"];

export function isReservedDomain(domain: string): boolean {
  return RESERVED_SUFFIXES.some((suffix) => domain === suffix || domain.endsWith(`.${suffix}`));
}

export const DEMO_TEMPLATES: ConfigurationTemplate[] = [
  {
    id: "00000000-0000-4000-8000-0000000c0001",
    code: "mutuelle-ci",
    version: 1,
    country_code: "CI",
    label: "Mutuelle santé Côte d'Ivoire (référence)",
    created_at: "2026-09-02T08:00:00Z",
    contents: { ledger_accounts: 18, rules: 6, plans: 2, coverages: 9, acts: 42, tariff_items: 42 },
  },
  {
    id: "00000000-0000-4000-8000-0000000c0002",
    code: "mutuelle-ci",
    version: 2,
    country_code: "CI",
    label: "Mutuelle santé Côte d'Ivoire (référence)",
    created_at: "2026-09-28T08:00:00Z",
    contents: { ledger_accounts: 18, rules: 7, plans: 3, coverages: 12, acts: 46, tariff_items: 46 },
  },
  {
    id: "00000000-0000-4000-8000-0000000c0003",
    code: "mutuelle-sn",
    version: 1,
    country_code: "SN",
    label: "Mutuelle santé Sénégal (référence)",
    created_at: "2026-09-15T08:00:00Z",
    contents: { ledger_accounts: 17, rules: 6, plans: 2, coverages: 9, acts: 39, tariff_items: 39 },
  },
];

export const INITIAL_BRANDING: BrandingSettings = {
  display_name: "Mutuelle MulemaCare (démonstration)",
  logo: null,
  theme: {},
  custom_domain: null,
  legal_notice: null,
  privacy_notice: null,
  customized: false,
  updated_at: null,
  custom_domain_status: null,
  custom_domain_verification: null,
};

/** Identifiants publics déjà pris dans l'instance de démonstration. */
export const TAKEN_SLUGS = ["mulemacare-ci-demo", "mulemacare-plateforme", "lagune-sante", "teranga-assurances"];

export interface MockProblem {
  status: number;
  code: "BRD-01" | "BRD-02" | "BRD-03" | "BRD-04" | "BRD-05" | "BRD-06" | "VAL-01" | "ORG-01" | "ORG-02";
  message: string;
  action: string;
  errors?: FieldError[];
}

const DOMAIN = /^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;
const PLAIN = /^[^<>\u0000-\u001f\u007f]+$/;
const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const label = (theme: string) => (theme === "light" ? "clair" : "sombre");
const ratio = (r: number) => r.toFixed(2).replace(".", ",");

/** Garde de `updateBrandingRequest` ; renvoie le problème ou les réglages enregistrés. */
export function checkBrandingUpdate(body: unknown, now: string, current: BrandingSettings = INITIAL_BRANDING, newToken: () => string = randomToken): MockProblem | BrandingSettings {
  const val = (errors: FieldError[]): MockProblem => ({ status: 422, code: "VAL-01", message: "Certaines informations sont invalides.", action: "Corrigez les champs signalés puis recommencez.", errors });
  if (!isRecord(body)) return val([{ field: "body", message: "Objet attendu." }]);
  const known = ["display_name", "logo", "theme", "custom_domain", "legal_notice", "privacy_notice"];
  const unknown = Object.keys(body).filter((k) => !known.includes(k));
  if (unknown.length) return val(unknown.map((field) => ({ field, message: "Champ inconnu." })));
  const name = body.display_name;
  if (typeof name !== "string" || name.length < 1 || name.length > 80 || !PLAIN.test(name)) return val([{ field: "display_name", message: "1 à 80 caractères, sans balise." }]);
  const domain = body.custom_domain ?? null;
  if (domain !== null && (typeof domain !== "string" || domain.length > 253 || !DOMAIN.test(domain))) return val([{ field: "custom_domain", message: "Domaine attendu, en minuscules (exemple : sante.mutuelle.ci)." }]);
  for (const field of ["legal_notice", "privacy_notice"] as const) {
    const v = body[field] ?? null;
    if (v !== null && (typeof v !== "string" || v.length > 4000 || /[<>]/.test(v))) return val([{ field, message: "Texte brut de 4 000 caractères au plus." }]);
  }

  const parsed = parseBrandTheme(body.theme ?? {});
  if ("errors" in parsed) {
    return {
      status: 422,
      code: "BRD-02",
      message: "Seuls quelques jetons de couleur se personnalisent, au format #RRGGBB.",
      action: "Retirez les jetons signalés ou corrigez leur couleur.",
      errors: parsed.errors.map((field) => ({ field, message: `Jeton non personnalisable ou couleur hors format. Jetons admis : ${OVERRIDABLE_TOKENS.join(", ")}.` })),
    };
  }
  const problems = brandProblems(parsed.theme);
  if (problems.length > 0) {
    return {
      status: 422,
      code: "BRD-01",
      message: "Ces couleurs ne sont pas assez lisibles (contraste WCAG AA).",
      action: "Choisissez une couleur plus foncée en clair ou plus claire en sombre.",
      errors: problems.map((p) => ({
        field: `theme.${p.theme}.${p.token}`,
        message:
          p.kind === "statut"
            ? `Thème ${label(p.theme)} : l'accent reprend une couleur de statut (ok, attention, critique, en cours) ; choisissez une autre couleur.`
            : `Thème ${label(p.theme)} : ${p.pair?.[0]} sur ${p.pair?.[1]} donne ${ratio(p.ratio ?? 0)}:1, il faut au moins ${String(p.minimum).replace(".", ",")}:1 (WCAG AA).`,
      })),
    };
  }
  const logo = body.logo ?? null;
  if (logo !== null && !safeLogoSrc(logo)) {
    return { status: 422, code: "BRD-03", message: "Ce logo est refusé : il pourrait s'exécuter ou venir d'un site non autorisé.", action: "Envoyez une image PNG, WebP, JPEG ou un SVG simple de 32 Ko au plus.", errors: [{ field: "logo", message: "Logo refusé." }] };
  }
  if (typeof domain === "string" && isReservedDomain(domain)) {
    return { status: 422, code: "BRD-05", message: "Ce domaine est réservé et ne peut pas être déclaré.", action: "Déclarez un domaine qui appartient à votre organisation.", errors: [{ field: "custom_domain", message: "Domaine réservé." }] };
  }
  if (domain === TAKEN_DOMAIN) {
    return { status: 409, code: "BRD-04", message: "Ce domaine est déjà déclaré par une autre organisation.", action: "Vérifiez le domaine ou contactez l'équipe de la plateforme.", errors: [{ field: "custom_domain", message: "Domaine déjà déclaré." }] };
  }
  const theme: BrandTheme = {};
  for (const t of THEMES) {
    const overrides = parsed.theme[t];
    if (overrides && Object.keys(overrides).length > 0) theme[t] = Object.fromEntries(Object.entries(overrides).map(([k, v]) => [k, normalizeHex(v)]));
  }
  return {
    display_name: name,
    logo: logo as BrandingSettings["logo"],
    theme,
    custom_domain: domain as string | null,
    legal_notice: (body.legal_notice ?? null) as string | null,
    privacy_notice: (body.privacy_notice ?? null) as string | null,
    customized: true,
    updated_at: now,
    ...domainProof(domain as string | null, current, newToken),
  };
}

function randomToken(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Le même domaine garde sa preuve ; un domaine nouveau ou changé repart « en attente », nouveau jeton. */
function domainProof(domain: string | null, current: BrandingSettings, newToken: () => string): Pick<BrandingSettings, "custom_domain_status" | "custom_domain_verification"> {
  if (!domain) return { custom_domain_status: null, custom_domain_verification: null };
  if (domain === current.custom_domain && current.custom_domain_verification) {
    return { custom_domain_status: current.custom_domain_status, custom_domain_verification: current.custom_domain_verification };
  }
  return {
    custom_domain_status: "en_attente_de_verification",
    custom_domain_verification: { record_type: "TXT", record_name: `_mulemacare-verification.${domain}`, record_value: `mulemacare-verification=${newToken()}` },
  };
}

/** `verifyBrandingDomain` (démonstration du port DNS) : BRD-06 sans domaine ou sans TXT publié. */
export function checkDomainVerification(current: BrandingSettings): MockProblem | BrandingSettings {
  if (!current.custom_domain || current.custom_domain.startsWith(UNPROVEN_DOMAIN_PREFIX)) {
    return {
      status: 422,
      code: "BRD-06",
      message: current.custom_domain ? "L'enregistrement DNS de vérification est introuvable ou différent." : "Aucun domaine personnalisé n'est déclaré.",
      action: current.custom_domain ? "Publiez l'enregistrement TXT indiqué chez votre hébergeur DNS, attendez sa propagation, puis recommencez." : "Déclarez d'abord un domaine et enregistrez la marque.",
    };
  }
  if (isReservedDomain(current.custom_domain)) {
    return { status: 422, code: "BRD-05", message: "Ce domaine est réservé et ne peut pas être déclaré.", action: "Déclarez un domaine qui appartient à votre organisation." };
  }
  return { ...current, custom_domain_status: "verifie" };
}

const SLUG = /^[a-z0-9][a-z0-9-]{1,62}$/;
const CODE = /^[a-z0-9][a-z0-9-]{1,39}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Garde de `createOrganization` (mêmes codes que l'API) ; renvoie le problème ou l'accueil. */
export function checkCreateOrganization(
  body: unknown,
  ctx: { takenSlugs: string[]; templates: ConfigurationTemplate[]; newId: () => string },
): MockProblem | OrganizationOnboarding {
  const errors: FieldError[] = [];
  if (!isRecord(body)) return { status: 422, code: "VAL-01", message: "Certaines informations sont invalides.", action: "Corrigez les champs signalés puis recommencez.", errors: [{ field: "body", message: "Objet attendu." }] };
  const { slug, name, country_code: country, capabilities, regulator, first_manager: manager, template } = body;
  if (typeof slug !== "string" || !SLUG.test(slug)) errors.push({ field: "slug", message: "2 à 63 caractères : minuscules, chiffres, tirets." });
  if (typeof name !== "string" || name.length < 1 || name.length > 120) errors.push({ field: "name", message: "1 à 120 caractères." });
  if (country !== "CI" && country !== "SN") errors.push({ field: "country_code", message: "CI ou SN." });
  const caps = Array.isArray(capabilities) ? capabilities : [];
  if (caps.length < 1 || new Set(caps).size !== caps.length || caps.some((c) => !["porteur_de_risque", "gestionnaire", "distributeur"].includes(String(c)))) {
    errors.push({ field: "capabilities", message: "Au moins une capacité parmi porteur_de_risque, gestionnaire, distributeur." });
  }
  if (regulator !== undefined && regulator !== null && (typeof regulator !== "string" || regulator.length > 40)) errors.push({ field: "regulator", message: "40 caractères au plus." });
  const m = isRecord(manager) ? manager : {};
  if (typeof m.idp_subject !== "string" || m.idp_subject.length < 1 || m.idp_subject.length > 200) errors.push({ field: "first_manager.idp_subject", message: "1 à 200 caractères." });
  if (typeof m.display_name !== "string" || m.display_name.length < 1 || m.display_name.length > 120) errors.push({ field: "first_manager.display_name", message: "1 à 120 caractères." });
  if (m.email !== undefined && (typeof m.email !== "string" || !EMAIL.test(m.email))) errors.push({ field: "first_manager.email", message: "Adresse e-mail invalide." });
  const tpl = isRecord(template) ? template : {};
  if (typeof tpl.code !== "string" || !CODE.test(tpl.code)) errors.push({ field: "template.code", message: "Code de gabarit invalide." });
  if (errors.length) return { status: 422, code: "VAL-01", message: "Certaines informations sont invalides.", action: "Corrigez les champs signalés puis recommencez.", errors };

  if (ctx.takenSlugs.includes(slug as string)) {
    return { status: 409, code: "ORG-01", message: "Cet identifiant public d'organisation est déjà utilisé.", action: "Choisissez un autre identifiant (lettres minuscules, chiffres, tirets)." };
  }
  const versions = ctx.templates.filter((t) => t.code === tpl.code && t.country_code === country);
  const chosen = typeof tpl.version === "number" ? versions.find((t) => t.version === tpl.version) : versions.sort((a, b) => b.version - a.version)[0];
  if (!chosen) {
    return { status: 422, code: "ORG-02", message: "Ce gabarit de configuration est introuvable ou prévu pour un autre pays.", action: "Choisissez un gabarit du même pays dans la liste des gabarits." };
  }
  const id = ctx.newId();
  return {
    organization: {
      id,
      slug: slug as string,
      name: name as string,
      country_code: country as "CI" | "SN",
      timezone: country === "SN" ? "Africa/Dakar" : "Africa/Abidjan",
      currency: "XOF",
      capabilities: caps as OrganizationOnboarding["organization"]["capabilities"],
    },
    first_manager: {
      id: ctx.newId(),
      display_name: m.display_name as string,
      email: (m.email as string | undefined) ?? null,
      status: "active",
      roles: [
        { role: "gestionnaire", provider_id: null, employer_id: null },
        { role: "admin", provider_id: null, employer_id: null },
      ],
    },
    template: { code: chosen.code, version: chosen.version },
    copied: chosen.contents,
  };
}
