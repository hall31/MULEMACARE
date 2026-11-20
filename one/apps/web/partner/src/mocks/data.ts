/**
 * Données de démonstration FICTIVES des espaces assureur et employeur (aucune personne réelle :
 * établissements et employeurs inventés, suffixés « fictif »). Les agrégats suivent les règles de
 * l'API (apps/api/partners/privacy.py) : seuil k = 5 personnes, effectif publié par palier, masque
 * complémentaire des statuts, catégories et prestataires sous le seuil fondus dans
 * `autres_regroupes`. Une période courte fait donc apparaître des cellules masquées, comme en vrai.
 * CR-P3-02 : période élargie aux semaines civiles entières et coupée à la dernière semaine
 * terminée (la période PUBLIÉE est rendue), comptes publiés au plancher du palier, montants
 * arrondis au millier : aucune valeur exacte.
 * Chaque réponse est validée contre specs/openapi.yaml (tests/unit/contract.test.ts).
 */
import type { BenefitCategory, CurrentUser, EmployerConsumption, EmployerContract, EmployerContractList, InsurerPortfolio, KAnonymousValue, Organization, StatusCount } from "@/api/types";
import type { DemoRole } from "@/lib/session";

export const K = 5;
const BANDS = [5, 10, 20, 50, 100];
export const OTHERS = "autres_regroupes";

const uuid = (n: number) => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;

export const ORGANIZATION: Organization = {
  id: uuid(0x301),
  slug: "assurances-lagune-vie",
  name: "Assurances Lagune Vie (démonstration)",
  country_code: "CI",
  timezone: "Africa/Abidjan",
  currency: "XOF",
  capabilities: ["porteur_de_risque"],
};

export const EMPLOYER_AKWABA = uuid(0x401);
export const EMPLOYER_CACAO = uuid(0x402);

export const DEMO_USERS: Record<DemoRole, CurrentUser> = {
  assureur: {
    user: { id: uuid(0x911), display_name: "Kouadio Brou", email: "actuariat@lagune-vie.invalid", status: "active", roles: [{ role: "assureur", provider_id: null, employer_id: null }] },
    organization: ORGANIZATION,
    roles: [{ role: "assureur", provider_id: null, employer_id: null }],
  },
  employeur: {
    user: { id: uuid(0x912), display_name: "Nadia Ouattara", email: "rh@akwaba-logistique.invalid", status: "active", roles: [{ role: "employeur", provider_id: null, employer_id: EMPLOYER_AKWABA }] },
    organization: ORGANIZATION,
    roles: [{ role: "employeur", provider_id: null, employer_id: EMPLOYER_AKWABA }],
  },
};

// ------------------------------------------------------------------ k-anonymat (miroir de l'API)
interface Cell {
  key: string;
  count: number;
  amount: number;
  people: number;
}

export function band(people: number): number {
  return Math.max(...BANDS.filter((b) => b <= people));
}

export function kv(value: number, people: number): KAnonymousValue {
  return people < K ? { status: "masque", value: null, contributors: null } : { status: "disponible", value, contributors: band(people) };
}

/** Compte (adhérents, dossiers) : jamais exact, plancher du palier (CR-P3-02). */
export function kvCount(count: number, people: number): KAnonymousValue {
  return people < K || count < K ? { status: "masque", value: null, contributors: null } : { status: "disponible", value: band(count), contributors: band(people) };
}

/** Montant : arrondi au millier de francs CFA (CR-P3-02). */
export function kvAmount(amount: number, people: number): KAnonymousValue {
  return kv(Math.round(amount / 1000) * 1000, people);
}

const MASKED: KAnonymousValue = { status: "masque", value: null, contributors: null };

/** Liste fixe (statuts) : masque complémentaire jusqu'à ce que les masqués réunis portent k personnes. */
function maskCells(cells: Cell[]): Set<string> {
  const hidden = cells.filter((c) => c.people < K);
  const shown = cells.filter((c) => c.people >= K).sort((a, b) => a.people - b.people || a.amount - b.amount);
  while (hidden.length > 0 && shown.length > 0 && hidden.reduce((s, c) => s + c.people, 0) < K) hidden.push(shown.shift()!);
  return new Set(cells.filter((c) => !hidden.includes(c)).map((c) => c.key));
}

/** Liste ouverte (catégories, prestataires) : sous le seuil, fondu dans « autres », grossi jusqu'à k. */
function foldCells(cells: Cell[], limit?: number): { shown: Cell[]; others: Cell | null } {
  const ordered = [...cells].sort((a, b) => b.amount - a.amount || b.people - a.people || a.key.localeCompare(b.key));
  let shown = ordered.filter((c) => c.people >= K);
  if (limit !== undefined) shown = shown.slice(0, limit);
  const rest = ordered.filter((c) => !shown.includes(c));
  while (rest.length > 0 && shown.length > 0 && rest.reduce((s, c) => s + c.people, 0) < K) rest.push(shown.pop()!);
  const others = rest.length ? { key: OTHERS, count: rest.reduce((s, c) => s + c.count, 0), amount: rest.reduce((s, c) => s + c.amount, 0), people: rest.reduce((s, c) => s + c.people, 0) } : null;
  return { shown, others };
}

function statuses(cells: Cell[]): StatusCount[] {
  const visible = maskCells(cells);
  return cells.map((c) => ({ status: c.key as StatusCount["status"], count: visible.has(c.key) ? kvCount(c.count, c.people) : MASKED }));
}

function categories(cells: Cell[]): BenefitCategory[] {
  const { shown, others } = foldCells(cells.filter((c) => c.people > 0));
  return [...shown, ...(others ? [others] : [])].map((c) => ({ category: c.key, claims: kvCount(c.count, c.people), covered_xof: kvAmount(c.amount, c.people) }));
}

// ------------------------------------------------------------------ périodes
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000) + 1;
}

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function addDays(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);
}

const mondayOf = (date: string) => addDays(date, -((new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7));

/**
 * Période PUBLIÉE (CR-P3-02) : du lundi de la semaine de `from` au dimanche de la semaine de `to`,
 * coupée au dernier dimanche terminé ; null si aucune semaine terminée (422 VAL-01).
 */
export function publishedPeriod(from: string, to: string): { from: string; to: string } | null {
  const start = mondayOf(from);
  const lastSunday = addDays(mondayOf(today()), -1);
  const sunday = addDays(mondayOf(to), 6);
  const end = sunday < lastSunday ? sunday : lastSunday;
  return start > end ? null : { from: start, to: end };
}

/** Durée de la période publiée en mois de 30 jours (les soins de démonstration s'y répartissent). */
function elapsedFactor(from: string, to: string): number {
  return to < from ? 0 : daysBetween(from, to) / 30;
}

const scale = (n: number, f: number) => Math.round(n * f);

// ------------------------------------------------------------------ assureur
const CATEGORY_BASE: [string, number, number, number][] = [
  // catégorie, personnes, dossiers, part mutuelle (FCFA) sur 30 jours
  ["pharmacie", 120, 210, 3_150_000],
  ["consultation", 96, 140, 2_380_000],
  ["hospitalisation", 9, 9, 4_950_000],
  ["analyses", 41, 52, 1_480_000],
  ["maternite", 3, 3, 1_200_000],
  ["imagerie", 6, 7, 690_000],
  ["dentaire", 2, 2, 180_000],
];

const PROVIDER_BASE: [number, string, number, number, number][] = [
  [0x501, "Clinique Les Palmiers (fictive)", 38, 52, 5_420_000],
  [0x502, "Pharmacie du Plateau (fictive)", 74, 121, 1_910_000],
  [0x503, "Laboratoire Lagune Analyses (fictif)", 33, 41, 1_190_000],
  [0x504, "Centre médical Riviera (fictif)", 52, 70, 1_160_000],
  [0x505, "Pharmacie Cocody Rond-Point (fictive)", 46, 89, 1_240_000],
  [0x506, "Cabinet dentaire Treichville (fictif)", 2, 2, 180_000],
  [0x507, "Centre d'imagerie Marcory (fictif)", 6, 7, 690_000],
];

export function insurerPortfolio(from: string, to: string): InsurerPortfolio {
  const f = elapsedFactor(from, to);
  const members: Cell[] = [
    { key: "actif", count: 412, amount: 0, people: 412 },
    { key: "carence", count: 23, amount: 0, people: 23 },
    { key: "suspendu", count: 4, amount: 0, people: 4 },
  ];
  const cats: Cell[] = CATEGORY_BASE.map(([key, p, c, a]) => ({ key, people: scale(p, f), count: scale(c, f), amount: scale(a, f) }));
  const providerCells: Cell[] = PROVIDER_BASE.map(([id, , p, c, a]) => ({ key: uuid(id), people: scale(p, f), count: scale(c, f), amount: scale(a, f) }));
  const { shown, others } = foldCells(providerCells.filter((c) => c.people > 0), 5);
  const claimants = Math.round(cats.reduce((s, c) => s + c.people, 0) * 0.82);
  const claimsCost = cats.reduce((s, c) => s + c.amount, 0);
  const payers = scale(380, f);
  const premiums = payers * 27_500;
  return {
    period_from: from,
    period_to: to,
    generated_at: new Date().toISOString(),
    k_anonymity_threshold: 5,
    currency: "XOF",
    members_total: kvCount(439, 439),
    members_by_status: statuses(members),
    premiums_xof: kvAmount(premiums, payers),
    claims_cost_xof: kvAmount(claimsCost, claimants),
    loss_ratio_bp: premiums > 0 ? kv(Math.round((claimsCost / premiums) * 10_000), Math.min(claimants, payers)) : MASKED,
    benefits_by_category: categories(cats),
    top_providers: shown.map((c) => ({ provider_id: c.key, name: PROVIDER_BASE.find(([id]) => uuid(id) === c.key)![1], claims: kvCount(c.count, c.people), covered_xof: kvAmount(c.amount, c.people) })),
    other_providers: others ? { claims: kvCount(others.count, others.people), covered_xof: kvAmount(others.amount, others.people) } : { claims: MASKED, covered_xof: MASKED },
    decision_delay_mean_ms: kv(9_360_000, claimants),
    automation_rate_bp: kv(7_120, claimants),
  };
}

const FORMULA = /^[=+\-@]/;
const cell = (text: string) => (FORMULA.test(text) ? `'${text}` : text);

/** CSV de `exportInsurerPortfolio` : `section;cle;statut;valeur;effectif;unite`, masques compris. */
export function portfolioCsv(p: InsurerPortfolio): string {
  const rows: [string, string, KAnonymousValue, string][] = [
    ["adherents", "total", p.members_total, "nombre"],
    ...p.members_by_status.map((s): [string, string, KAnonymousValue, string] => ["adherents", s.status, s.count, "nombre"]),
    ["primes", "encaissees", p.premiums_xof, "xof"],
    ["sinistres", "part_mutuelle", p.claims_cost_xof, "xof"],
    ["ratio", "sinistres_sur_primes", p.loss_ratio_bp, "pour_dix_mille"],
  ];
  for (const c of p.benefits_by_category) rows.push(["categorie_dossiers", c.category, c.claims, "nombre"], ["categorie_part_mutuelle", c.category, c.covered_xof, "xof"]);
  for (const pr of p.top_providers) rows.push(["prestataire_dossiers", pr.name, pr.claims, "nombre"], ["prestataire_part_mutuelle", pr.name, pr.covered_xof, "xof"]);
  rows.push(
    ["autres_prestataires", "dossiers", p.other_providers.claims, "nombre"],
    ["autres_prestataires", "part_mutuelle", p.other_providers.covered_xof, "xof"],
    ["decision", "delai_moyen", p.decision_delay_mean_ms, "millisecondes"],
    ["decision", "part_automatique", p.automation_rate_bp, "pour_dix_mille"],
  );
  const lines = ["section;cle;statut;valeur;effectif;unite", `periode;${p.period_from}/${p.period_to};;;;`];
  for (const [section, key, v, unit] of rows) lines.push([section, cell(key), v.status, v.value ?? "", v.contributors ?? "", unit].join(";"));
  return `${lines.join("\r\n")}\r\n`;
}

// ------------------------------------------------------------------ employeur
const GROUPS: { id: string; name: string; members: [number, number, number]; categories: [string, number, number, number][]; start: string; endOffset: number | null }[] = [
  {
    id: EMPLOYER_AKWABA,
    name: "Groupe Akwaba Logistique (fictif)",
    members: [184, 12, 3],
    categories: [
      ["pharmacie", 48, 81, 1_210_000],
      ["consultation", 39, 55, 930_000],
      ["analyses", 14, 17, 410_000],
      ["hospitalisation", 2, 2, 1_100_000],
      ["maternite", 1, 1, 400_000],
    ],
    start: "2025-11-01",
    endOffset: 42,
  },
  {
    id: EMPLOYER_CACAO,
    name: "Coopérative Cacao Sud (fictive)",
    members: [7, 1, 0],
    categories: [
      ["pharmacie", 3, 4, 52_000],
      ["consultation", 2, 2, 31_000],
    ],
    start: "2025-09-15",
    endOffset: -12,
  },
];

export function employerConsumption(from: string, to: string): EmployerConsumption {
  const f = elapsedFactor(from, to);
  return {
    period_from: from,
    period_to: to,
    generated_at: new Date().toISOString(),
    k_anonymity_threshold: 5,
    currency: "XOF",
    groups: GROUPS.map((g) => {
      const [actif, carence, suspendu] = g.members;
      const cats: Cell[] = g.categories.map(([key, p, c, a]) => ({ key, people: scale(p, f), count: scale(c, f), amount: scale(a, f) }));
      const claimants = Math.round(cats.reduce((s, c) => s + c.people, 0) * 0.8);
      const total = actif + carence + suspendu;
      return {
        employer_id: g.id,
        name: g.name,
        members_total: kvCount(total, total),
        members_by_status: statuses([
          { key: "actif", count: actif, amount: 0, people: actif },
          { key: "carence", count: carence, amount: 0, people: carence },
          { key: "suspendu", count: suspendu, amount: 0, people: suspendu },
        ]),
        claims: kvCount(cats.reduce((s, c) => s + c.count, 0), claimants),
        covered_xof: kvAmount(cats.reduce((s, c) => s + c.amount, 0), claimants),
        benefits_by_category: categories(cats),
      };
    }),
  };
}

export function employerContracts(withinDays: number): EmployerContractList {
  const asOf = today();
  const extra: EmployerContract[] = [
    { employer_id: uuid(0x403), name: "Transports Bandama (fictif)", contract_start: "2026-01-01", contract_end: addDays(asOf, 200), days_remaining: 200, status: "en_cours", members_total: kvCount(57, 57) },
    { employer_id: uuid(0x404), name: "Collège Les Flamboyants (fictif)", contract_start: "2024-09-01", contract_end: null, days_remaining: null, status: "sans_echeance", members_total: kvCount(23, 23) },
  ];
  const items: EmployerContract[] = [
    ...GROUPS.map((g): EmployerContract => {
      const end = g.endOffset === null ? null : addDays(asOf, g.endOffset);
      const total = g.members.reduce((s, n) => s + n, 0);
      return { employer_id: g.id, name: g.name, contract_start: g.start, contract_end: end, days_remaining: g.endOffset, status: "en_cours", members_total: kvCount(total, total) };
    }),
    ...extra,
  ].map((c) => ({ ...c, status: c.days_remaining === null ? "sans_echeance" : c.days_remaining < 0 ? "echu" : c.days_remaining <= withinDays ? "a_echeance" : "en_cours" }));
  return { as_of: asOf, within_days: withinDays, items };
}
