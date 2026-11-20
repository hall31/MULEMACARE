/**
 * Jeu de démonstration FICTIF de la console (lot L6). Aucune personne réelle : noms,
 * numéros et établissements reprennent le prototype specs/design/prototype.html.
 * Les paramètres de produit et de règle suivent specs/seeds/demo.sql (valeurs « proto »).
 * Chaque réponse construite à partir de ces données est validée contre specs/openapi.yaml
 * (tests/unit/contract.test.ts).
 */
import type {
  ClaimDecisionRecord,
  ClaimDetail,
  ClaimItem,
  ClaimStatus,
  Contribution,
  CurrentUser,
  Entitlements,
  LedgerAccount,
  LedgerEntry,
  Member,
  Organization,
  Plan,
  PlanVersion,
} from "@/api/types";
import type { DemoRole } from "@/lib/session";

const uuid = (n: number): string => `00000000-0000-4000-8000-${n.toString(16).padStart(12, "0")}`;

export const ORGANIZATION: Organization = {
  id: "00000000-0000-4000-8000-000000000001",
  slug: "mulemacare-ci-demo",
  name: "Mutuelle MulemaCare (démonstration)",
  country_code: "CI",
  timezone: "Africa/Abidjan",
  currency: "XOF",
  capabilities: ["porteur_de_risque", "gestionnaire"],
};

/** Organisation « plateforme » (Q-P3-01) : exploite l'instance, accueille les organisations. */
export const PLATFORM_ORGANIZATION: Organization = {
  id: "00000000-0000-4000-8000-000000000002",
  slug: "mulemacare-plateforme",
  name: "MulemaCare Plateforme (démonstration)",
  country_code: "CI",
  timezone: "Africa/Abidjan",
  currency: "XOF",
  capabilities: ["plateforme"],
};

export const DEMO_USERS: Record<DemoRole, CurrentUser> = {
  gestionnaire: {
    user: {
      id: uuid(0x901),
      display_name: "Mariam Coulibaly",
      email: "gestion@mulemacare.invalid",
      status: "active",
      roles: [{ role: "gestionnaire", provider_id: null, employer_id: null }],
    },
    organization: ORGANIZATION,
    roles: [{ role: "gestionnaire", provider_id: null, employer_id: null }],
  },
  medecin_conseil: {
    user: {
      id: uuid(0x902),
      display_name: "Dr Serge N'Guessan",
      email: "medecin-conseil@mulemacare.invalid",
      status: "active",
      roles: [{ role: "medecin_conseil", provider_id: null, employer_id: null }],
    },
    organization: ORGANIZATION,
    roles: [{ role: "medecin_conseil", provider_id: null, employer_id: null }],
  },
  admin: {
    user: {
      id: uuid(0x903),
      display_name: "Fatou Diabaté",
      email: "admin@mulemacare.invalid",
      status: "active",
      roles: [{ role: "admin", provider_id: null, employer_id: null }],
    },
    organization: ORGANIZATION,
    roles: [{ role: "admin", provider_id: null, employer_id: null }],
  },
  admin_plateforme: {
    user: {
      id: uuid(0x904),
      display_name: "Ibrahim Touré",
      email: "plateforme@mulemacare.invalid",
      status: "active",
      roles: [{ role: "admin_plateforme", provider_id: null, employer_id: null }],
    },
    organization: PLATFORM_ORGANIZATION,
    roles: [{ role: "admin_plateforme", provider_id: null, employer_id: null }],
  },
};

// ------------------------------------------------------------------ temps relatif
const NOW = Date.now();
const minutesAgo = (m: number): string => new Date(NOW - m * 60_000).toISOString();
const dayOf = (iso: string): string => iso.slice(0, 10);
const addMinutes = (iso: string, m: number): string => new Date(Date.parse(iso) + m * 60_000).toISOString();
const monthStart = (offset: number): string => {
  const d = new Date(NOW);
  const first = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - offset, 1));
  return first.toISOString().slice(0, 10);
};
const addDays = (date: string, days: number): string =>
  new Date(Date.parse(`${date}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10);

// ------------------------------------------------------------------ produits
function planVersion(
  n: number,
  planId: string,
  version: number,
  validFrom: string,
  validTo: string | null,
  state: PlanVersion["state"],
  rateBp: number,
  ceiling: number,
  waitingDays: number,
  monthly: number,
): PlanVersion {
  return {
    id: uuid(0x300 + n),
    plan_id: planId,
    version,
    valid_from: validFrom,
    valid_to: validTo,
    state,
    coverage_rate_bp: rateBp,
    family_annual_ceiling_xof: ceiling,
    waiting_period_days: waitingDays,
    monthly_contribution_xof: monthly,
    currency: "XOF",
    coverages: [
      { category: "soins_courants", label: "Soins courants", coverage_rate_bp: null, annual_limit_xof: null, limit_scope: "famille" },
      { category: "hospitalisation", label: "Hospitalisation", coverage_rate_bp: null, annual_limit_xof: Math.round((ceiling * 0.6) / 1000) * 1000, limit_scope: "famille" },
      { category: "optique", label: "Optique", coverage_rate_bp: 6000, annual_limit_xof: 90_000, limit_scope: "beneficiaire" },
      { category: "dentaire", label: "Dentaire", coverage_rate_bp: 6000, annual_limit_xof: 150_000, limit_scope: "beneficiaire" },
      { category: "maternite", label: "Maternité", coverage_rate_bp: null, annual_limit_xof: 400_000, limit_scope: "famille" },
    ],
  };
}

const PLAN_OR_ID = uuid(0x201);
const PLAN_ESS_ID = uuid(0x202);
const PLAN_JEUNE_ID = uuid(0x203);

export const PLAN_FAMILLE_OR: Plan = {
  id: PLAN_OR_ID,
  code: "FAMILLE-OR",
  name: "Santé Famille Or",
  status: "active",
  current_version_id: uuid(0x302),
  versions: [
    planVersion(1, PLAN_OR_ID, 1, "2025-01-01", "2025-12-31", "cloturee", 8000, 2_500_000, 90, 25_000),
    planVersion(2, PLAN_OR_ID, 2, "2026-01-01", "2026-12-31", "en_vigueur", 8000, 3_000_000, 60, 27_500),
    planVersion(3, PLAN_OR_ID, 3, "2027-01-01", null, "brouillon", 8000, 3_200_000, 60, 27_500),
  ],
};

export const DEMO_PLANS: Plan[] = [
  PLAN_FAMILLE_OR,
  {
    id: PLAN_ESS_ID,
    code: "ESSENTIEL",
    name: "Santé Essentiel",
    status: "active",
    current_version_id: uuid(0x311),
    versions: [planVersion(0x11, PLAN_ESS_ID, 1, "2026-01-01", "2026-12-31", "en_vigueur", 7000, 1_200_000, 60, 16_000)],
  },
  {
    id: PLAN_JEUNE_ID,
    code: "JEUNE",
    name: "Santé Jeune",
    status: "active",
    current_version_id: uuid(0x321),
    versions: [planVersion(0x21, PLAN_JEUNE_ID, 1, "2026-01-01", "2026-12-31", "en_vigueur", 6000, 600_000, 60, 9_000)],
  },
];

const planByCode = (code: string): Plan => DEMO_PLANS.find((p) => p.code === code)!;
const currentVersion = (plan: Plan): PlanVersion => plan.versions.find((v) => v.id === plan.current_version_id)!;

// ------------------------------------------------------------------ prestataires
export const PROVIDERS = [
  { id: uuid(0x401), name: "Clinique Les Palmiers · Cocody" },
  { id: uuid(0x402), name: "Polyclinique du Plateau" },
  { id: uuid(0x403), name: "Pharmacie Riviera 3" },
  { id: uuid(0x404), name: "Laboratoire Marcory Centre" },
  { id: uuid(0x405), name: "Clinique Mermoz · Dakar" },
  { id: uuid(0x406), name: "Centre d'imagerie Deux-Plateaux" },
] as const;

// ------------------------------------------------------------------ adhérents
interface MemberSeed {
  n: number;
  number: string;
  given: string;
  family: string;
  birth: string;
  plan: string;
  status: Member["status"];
  enrolled: string;
  dependents: { given: string; rel: "conjoint" | "enfant"; birth: string }[];
  consumed: number;
  late: number; // nombre de cotisations mensuelles en retard, les plus récentes
  channel: NonNullable<Contribution["channel"]>;
}

const memberSeeds: MemberSeed[] = [
  { n: 1, number: "MC-00249218", given: "Koffi", family: "Yao", birth: "1981-04-12", plan: "FAMILLE-OR", status: "actif", enrolled: "2024-03-01",
    dependents: [{ given: "Adjoua", rel: "conjoint", birth: "1984-09-02" }, { given: "Kouamé", rel: "enfant", birth: "2017-02-20" }, { given: "Ama", rel: "enfant", birth: "2022-06-11" }],
    consumed: 1_110_000, late: 0, channel: "prelevement_employeur" },
  { n: 2, number: "MC-00928194", given: "Awa", family: "Koné", birth: "1990-11-30", plan: "FAMILLE-OR", status: "actif", enrolled: "2025-01-01",
    dependents: [{ given: "Issa", rel: "enfant", birth: "2019-01-15" }, { given: "Mariam", rel: "enfant", birth: "2022-08-03" }],
    consumed: 420_000, late: 0, channel: "wave" },
  { n: 3, number: "MC-00311407", given: "Mariama", family: "Diallo", birth: "1993-05-21", plan: "ESSENTIEL", status: "actif", enrolled: "2025-06-01",
    dependents: [{ given: "Ousmane", rel: "conjoint", birth: "1989-12-08" }],
    consumed: 1_020_000, late: 0, channel: "wave" },
  { n: 4, number: "MC-00187752", given: "Jean-Baptiste", family: "Kouassi", birth: "1976-02-14", plan: "ESSENTIEL", status: "suspendu", enrolled: "2024-09-01",
    dependents: [], consumed: 180_000, late: 3, channel: "orange_money" },
  { n: 5, number: "MC-00455190", given: "Fatou", family: "Ndiaye", birth: "1979-07-07", plan: "FAMILLE-OR", status: "actif", enrolled: "2024-02-01",
    dependents: [{ given: "Cheikh", rel: "conjoint", birth: "1975-03-19" }, { given: "Aïda", rel: "enfant", birth: "2008-10-10" }, { given: "Moussa", rel: "enfant", birth: "2012-04-25" }, { given: "Khady", rel: "enfant", birth: "2016-12-01" }],
    consumed: 2_640_000, late: 0, channel: "prelevement_employeur" },
  { n: 6, number: "MC-00502066", given: "Ibrahim", family: "Traoré", birth: "2001-08-18", plan: "JEUNE", status: "carence", enrolled: monthStart(0),
    dependents: [], consumed: 0, late: 0, channel: "mtn_momo" },
];

export const DEMO_MEMBERS: Member[] = memberSeeds.map((s) => {
  const version = currentVersion(planByCode(s.plan));
  return {
    id: uuid(0x100 + s.n),
    member_number: s.number,
    holder: {
      person_id: uuid(0x500 + s.n * 0x10),
      given_name: s.given,
      family_name: s.family,
      birth_date: s.birth,
      // Aucun numéro de téléphone, même fictif : il pourrait appartenir à quelqu'un.
      phone_e164: null,
    },
    plan_code: s.plan,
    employer_id: null,
    status: s.status,
    status_changed_at: s.status === "suspendu" ? minutesAgo(60 * 24 * 2) : `${s.enrolled}T08:00:00Z`,
    enrolled_on: s.enrolled,
    waiting_period_ends_on: addDays(s.enrolled, version.waiting_period_days),
    dependents: s.dependents.map((d, i) => ({
      id: uuid(0x600 + s.n * 0x10 + i),
      person_id: uuid(0x500 + s.n * 0x10 + i + 1),
      given_name: d.given,
      family_name: s.family,
      relationship: d.rel,
      valid_from: s.enrolled,
      valid_to: null,
    })),
  };
});

export function entitlementsFor(member: Member, at: string): Entitlements {
  const seed = memberSeeds.find((s) => s.number === member.member_number)!;
  const version = currentVersion(planByCode(member.plan_code));
  const ceiling = version.family_annual_ceiling_xof;
  return {
    member_id: member.id,
    at,
    status: member.status,
    rights_open: member.status === "actif",
    waiting_period_ends_on: member.waiting_period_ends_on,
    plan_version_id: version.id,
    family_annual_ceiling_xof: ceiling,
    consumed_xof: seed.consumed,
    remaining_xof: Math.max(0, ceiling - seed.consumed),
    currency: "XOF",
  };
}

export function contributionsFor(member: Member): Contribution[] {
  const seed = memberSeeds.find((s) => s.number === member.member_number)!;
  const monthly = currentVersion(planByCode(member.plan_code)).monthly_contribution_xof;
  const months = member.status === "carence" ? 1 : 4;
  return Array.from({ length: months }, (_, i) => {
    const period = monthStart(i);
    const late = i < seed.late;
    const due = addDays(period, 5);
    return {
      id: uuid(0x700 + seed.n * 0x10 + i),
      period_start: period,
      due_on: due,
      amount_xof: monthly,
      currency: "XOF" as const,
      status: late ? ("en_retard" as const) : ("payee" as const),
      paid_at: late ? null : `${addDays(period, 2)}T09:30:00Z`,
      channel: late ? null : seed.channel,
    };
  });
}

// ------------------------------------------------------------------ prises en charge
interface ClaimSeed {
  n: number;
  number: string;
  member: number;
  provider: number;
  minutesAgo: number;
  status: ClaimStatus;
  fraud: number;
  flagged?: boolean;
  rule: { code: string; version: number };
  acts: [string, string, number][]; // code, libellé de facturation, montant unitaire
}

const claimSeeds: ClaimSeed[] = [
  { n: 1, number: "PEC-26-09814", member: 0, provider: 0, minutesAgo: 12, status: "accordee_auto", fraud: 0.06, rule: { code: "R-12", version: 3 },
    acts: [["CONS-GEN", "Consultation généraliste", 25_000], ["NFS", "NFS (numération)", 8_000], ["ECG", "ECG", 15_000]] },
  { n: 2, number: "PEC-26-09813", member: 4, provider: 5, minutesAgo: 95, status: "en_revue", fraud: 0.18, rule: { code: "R-20", version: 2 },
    acts: [["IRM-GEN", "IRM genou", 185_000]] },
  { n: 3, number: "PEC-26-09811", member: 2, provider: 4, minutesAgo: 160, status: "en_revue", fraud: 0.11, rule: { code: "R-20", version: 2 },
    acts: [["ECHO", "Échographie", 35_000], ["CONS-SPE", "Consultation spécialiste", 27_000]] },
  { n: 4, number: "PEC-26-09807", member: 1, provider: 2, minutesAgo: 230, status: "payee", fraud: 0.03, rule: { code: "R-12", version: 3 },
    acts: [["PHARMA", "Délivrance pharmacie", 21_500]] },
  { n: 5, number: "PEC-26-09802", member: 4, provider: 3, minutesAgo: 370, status: "en_revue", fraud: 0.72, flagged: true, rule: { code: "R-20", version: 2 },
    acts: [["BIO-LIP", "Bilan lipidique", 24_000], ["BIO-HBA", "HbA1c", 18_000], ["BIO-HEP", "Bilan hépatique", 27_000], ["BIO-REN", "Bilan rénal", 27_000]] },
  { n: 6, number: "PEC-26-09796", member: 0, provider: 1, minutesAgo: 60 * 26, status: "payee", fraud: 0.04, rule: { code: "R-12", version: 3 },
    acts: [["CONS-SPE", "Consultation spécialiste", 35_500]] },
  { n: 7, number: "PEC-26-09790", member: 3, provider: 0, minutesAgo: 60 * 34, status: "refusee", fraud: 0.09, rule: { code: "R-01", version: 1 },
    acts: [["CONS-GEN", "Consultation généraliste", 25_000]] },
  { n: 8, number: "PEC-26-09785", member: 2, provider: 3, minutesAgo: 60 * 40, status: "pieces_demandees", fraud: 0.14, rule: { code: "R-20", version: 2 },
    acts: [["BIO-LIP", "Bilan lipidique", 24_000], ["BIO-REN", "Bilan rénal", 27_000], ["CONS-SPE", "Consultation spécialiste", 27_000]] },
  { n: 9, number: "PEC-26-09781", member: 1, provider: 0, minutesAgo: 60 * 49, status: "accordee_auto", fraud: 0.05, rule: { code: "R-12", version: 3 },
    acts: [["CONS-PED", "Consultation pédiatrie", 32_000], ["CRP", "CRP", 8_000]] },
];

const MEDECIN_ID = DEMO_USERS.medecin_conseil.user.id;

function buildClaim(seed: ClaimSeed): ClaimDetail {
  const member = DEMO_MEMBERS[seed.member]!;
  const provider = PROVIDERS[seed.provider]!;
  const version = currentVersion(planByCode(member.plan_code));
  const rateBp = version.coverage_rate_bp;
  const refused = seed.status === "refusee";
  const items: ClaimItem[] = seed.acts.map(([code, label, unit], i) => {
    const covered = refused ? 0 : Math.round((unit * rateBp) / 10_000);
    return { line_no: i + 1, act_code: code, label, quantity: 1, unit_amount_xof: unit, amount_xof: unit, covered_xof: covered };
  });
  const total = items.reduce((a, it) => a + it.amount_xof, 0);
  const covered = items.reduce((a, it) => a + it.covered_xof, 0);
  const requestedAt = minutesAgo(seed.minutesAgo);
  const ruleOutcome: ClaimDecisionRecord["outcome"] =
    seed.rule.code === "R-12" ? "accordee_auto" : seed.rule.code === "R-20" ? "en_revue" : "refusee";
  const decisions: ClaimDecisionRecord[] = [
    { sequence: 1, outcome: ruleOutcome, source: "regle", rule: seed.rule, reason_code: seed.rule.code, decided_by: null, decided_at: addMinutes(requestedAt, 0) },
  ];
  if (seed.status === "pieces_demandees") {
    decisions.push({ sequence: 2, outcome: "pieces_demandees", source: "humain", rule: null, reason_code: "PCS-01", decided_by: MEDECIN_ID, decided_at: addMinutes(requestedAt, 55) });
  }
  const authorized = seed.status === "accordee_auto" || seed.status === "payee";
  return {
    claim: {
      id: uuid(0x800 + seed.n),
      claim_number: seed.number,
      member_id: member.id,
      member_display_name: `${member.holder.given_name} ${member.holder.family_name}`,
      provider_id: provider.id,
      provider_name: provider.name,
      service_date: dayOf(requestedAt),
      requested_at: requestedAt,
      status: seed.status,
      total_xof: total,
      covered_xof: covered,
      currency: "XOF",
      fraud_score: seed.fraud,
      fraud_flagged: seed.flagged ?? false,
      rule: seed.rule,
    },
    patient_share_xof: total - covered,
    plan_version_id: version.id,
    review_due_at: seed.status === "en_revue" ? addMinutes(requestedAt, 120) : null,
    items,
    decisions,
    authorization: authorized
      ? {
          id: uuid(0x900 + seed.n),
          authorization_number: `ACC-${seed.number.slice(4)}`,
          kind: "en_ligne",
          status: "emise",
          covered_xof: covered,
          currency: "XOF",
          rule: seed.rule,
          issued_at: requestedAt,
          expires_at: null,
        }
      : null,
  };
}

export const DEMO_CLAIM_DETAILS: ClaimDetail[] = claimSeeds.map(buildClaim);
export const DEMO_CLAIMS = DEMO_CLAIM_DETAILS.map((d) => d.claim);

export const REVIEW_CLAIM = DEMO_CLAIMS.find((c) => c.claim_number === "PEC-26-09813")!;
export const AUTO_CLAIM = DEMO_CLAIMS.find((c) => c.claim_number === "PEC-26-09814")!;

/**
 * Motifs médicaux FICTIFS, détenus par le HealthOS simulé (base `clinical`), jamais par la base
 * assurance : ils ne sont servis que par GET /v1/claims/{id}/medical-reason au médecin-conseil.
 */
const HEALTHOS_REASONS: Record<string, string> = {
  [uuid(0x801)]: "Douleur thoracique atypique — bilan cardiaque (donnée fictive)",
  [uuid(0x802)]: "Suspicion de lésion méniscale après traumatisme du genou (donnée fictive)",
  [uuid(0x803)]: "Suivi de grossesse, deuxième trimestre (donnée fictive)",
  [uuid(0x804)]: "Angine bactérienne (donnée fictive)",
  [uuid(0x805)]: "Bilan de routine (donnée fictive)",
  [uuid(0x806)]: "Contrôle d'hypertension artérielle (donnée fictive)",
  [uuid(0x807)]: "Céphalées (donnée fictive)",
  [uuid(0x808)]: "Bilan métabolique (donnée fictive)",
  [uuid(0x809)]: "Fièvre de l'enfant (donnée fictive)",
};

export function medicalReasonFor(claimId: string): string {
  const reason = HEALTHOS_REASONS[claimId];
  if (!reason) throw new Error(`Aucun motif simulé pour ${claimId}`);
  return reason;
}

// ------------------------------------------------------------------ grand livre
export const LEDGER_ACCOUNTS: LedgerAccount[] = [
  { code: "4011", label: "Prestataires à payer", account_class: "passif" },
  { code: "5110", label: "Banque", account_class: "actif" },
  { code: "5121", label: "Mobile money · Wave", account_class: "actif" },
  { code: "5122", label: "Mobile money · Orange Money", account_class: "actif" },
  { code: "6011", label: "Prestations santé", account_class: "charge" },
  { code: "7061", label: "Cotisations acquises", account_class: "produit" },
];

const accountLabel = (code: string): string => LEDGER_ACCOUNTS.find((a) => a.code === code)!.label;

export function ledgerLines(lines: [string, number, number, { provider?: string; member?: string }?][]): LedgerEntry["lines"] {
  return lines.map(([code, debit, credit, refs], i) => ({
    line_no: i + 1,
    account_code: code,
    account_label: accountLabel(code),
    debit_xof: debit,
    credit_xof: credit,
    provider_id: refs?.provider ?? null,
    member_id: refs?.member ?? null,
  }));
}

function claimEntry(n: number, number: string, detail: ClaimDetail): LedgerEntry {
  const c = detail.claim;
  return {
    id: uuid(0xa00 + n),
    entry_number: number,
    accounting_date: dayOf(c.requested_at),
    posted_at: c.requested_at,
    label: `${c.claim_number} · accord tiers payant`,
    source_type: "prise_en_charge",
    source_id: c.id,
    reverses_entry_id: null,
    reversed_by_entry_id: null,
    currency: "XOF",
    lines: ledgerLines([
      ["6011", c.covered_xof, 0, { member: c.member_id }],
      ["4011", 0, c.covered_xof, { provider: c.provider_id }],
    ]),
  };
}

const detailByNumber = (number: string): ClaimDetail => DEMO_CLAIM_DETAILS.find((d) => d.claim.claim_number === number)!;
const awa = DEMO_MEMBERS[1]!;

export const DEMO_LEDGER: LedgerEntry[] = [
  claimEntry(1, "J-2026-0918402", detailByNumber("PEC-26-09814")),
  {
    id: uuid(0xa02),
    entry_number: "J-2026-0918399",
    accounting_date: dayOf(minutesAgo(50)),
    posted_at: minutesAgo(50),
    label: `Cotisation · ${awa.member_number} · payée par un proche`,
    source_type: "cotisation",
    source_id: uuid(0x720),
    reverses_entry_id: null,
    reversed_by_entry_id: null,
    currency: "XOF",
    lines: ledgerLines([["5121", 27_500, 0], ["7061", 0, 27_500, { member: awa.id }]]),
  },
  {
    id: uuid(0xa03),
    entry_number: "J-2026-0918391",
    accounting_date: dayOf(minutesAgo(200)),
    posted_at: minutesAgo(200),
    label: "Règlement groupé prestataires · lot 2026-39",
    source_type: "reglement",
    source_id: null,
    reverses_entry_id: null,
    reversed_by_entry_id: null,
    currency: "XOF",
    lines: ledgerLines([["4011", 4_812_300, 0], ["5122", 0, 4_812_300]]),
  },
  claimEntry(4, "J-2026-0918388", detailByNumber("PEC-26-09807")),
  {
    id: uuid(0xa05),
    entry_number: "J-2026-0918377",
    accounting_date: dayOf(minutesAgo(420)),
    posted_at: minutesAgo(420),
    label: "Contre-passation J-2026-0918201 · erreur de barème",
    source_type: "contre_passation",
    source_id: null,
    reverses_entry_id: uuid(0xa07),
    reversed_by_entry_id: null,
    currency: "XOF",
    lines: ledgerLines([["4011", 6_000, 0, { provider: PROVIDERS[1].id }], ["6011", 0, 6_000]]),
  },
  {
    id: uuid(0xa06),
    entry_number: "J-2026-0918350",
    accounting_date: dayOf(minutesAgo(600)),
    posted_at: minutesAgo(600),
    label: "Prélèvement employeur · 212 adhérents",
    source_type: "cotisation",
    source_id: null,
    reverses_entry_id: null,
    reversed_by_entry_id: null,
    currency: "XOF",
    lines: ledgerLines([["5110", 9_328_000, 0], ["7061", 0, 9_328_000]]),
  },
  {
    id: uuid(0xa07),
    entry_number: "J-2026-0918201",
    accounting_date: dayOf(minutesAgo(60 * 30)),
    posted_at: minutesAgo(60 * 30),
    label: "PEC-26-09760 · accord tiers payant",
    source_type: "prise_en_charge",
    source_id: null,
    reverses_entry_id: null,
    reversed_by_entry_id: uuid(0xa05),
    currency: "XOF",
    lines: ledgerLines([["6011", 6_000, 0], ["4011", 0, 6_000, { provider: PROVIDERS[1].id }]]),
  },
  claimEntry(8, "J-2026-0918230", detailByNumber("PEC-26-09796")),
  claimEntry(9, "J-2026-0918044", detailByNumber("PEC-26-09781")),
];

export { uuid as fixtureUuid };
