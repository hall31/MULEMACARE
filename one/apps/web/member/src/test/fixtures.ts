import type {
  ClaimTracking,
  CurrentUser,
  MyBeneficiaryList,
  MyCard,
  MyClaim,
  MyContributions,
  PublicPaymentLink,
  TrackingStep,
} from "@/api/types";

/**
 * Jeu de données FICTIF de l'espace adhérent, typé par le contrat (src/api/schema.d.ts généré
 * depuis specs/openapi.yaml) : une donnée hors contrat ne compile pas. Noms et établissements
 * repris de la planche (`specs/design/direction`), aucune personne réelle. Partagé par Vitest
 * (`contract.test.ts`) et par le mock Playwright (`e2e/mock-api.ts`).
 */
export const IDS = {
  user: "7c1e2d3f-4a5b-4c6d-8e7f-90a1b2c3d4e5",
  organization: "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9",
  member: "6b5a4938-2716-4a5b-8c7d-6e5f4a3b2c1d",
  planVersion: "2b3c4d5e-6f70-4812-9a3b-4c5d6e7f8091",
  awa: "5a0e6f1c-2b7d-4e1a-8c33-7d9e0a4b6c12",
  kouassi: "5b1c0d2e-3f40-4a51-8b62-7c83d94ea5f6",
  aya: "5c2d1e3f-4051-4b62-9c73-8d94ea05b607",
  cardAwa: "8a7b6c5d-4e3f-4a2b-9c1d-0e1f2a3b4c5d",
  cardKouassi: "8b8c7d6e-5f40-4b3c-8d2e-1f203b4c5d6e",
  claimPharmacy: "e1d2c3b4-a596-4877-8695-a4b3c2d1e0f1",
  claimClinic: "e2e3d4c5-b6a7-4988-9706-b5c4d3e2f102",
  claimRefused: "e3f4e5d6-c7b8-4a99-a817-c6d5e4f30213",
  octobre: "c0c0c0c0-0000-4000-8000-000000000010",
  septembre: "c0c0c0c0-0000-4000-8000-000000000009",
  aout: "c0c0c0c0-0000-4000-8000-000000000008",
} as const;

export const PAYMENT_TOKEN = "jeton-fictif-lien-de-paiement-0123456789abcdef";
export const EXPIRED_TOKEN = "jeton-fictif-lien-expire-0123456789abcdef-zz";
export const UNKNOWN_TOKEN = "jeton-fictif-lien-inconnu-0123456789abcdef-zz";

export const me: CurrentUser = {
  user: { id: IDS.user, display_name: "Awa Koné", email: null, status: "active", roles: [{ role: "adherent", member_id: IDS.member }] },
  organization: {
    id: IDS.organization,
    slug: "mulemacare-ci",
    name: "MulemaCare Côte d'Ivoire",
    country_code: "CI",
    timezone: "Africa/Abidjan",
    currency: "XOF",
    capabilities: ["porteur_de_risque"],
  },
  roles: [{ role: "adherent", member_id: IDS.member }],
};

const entitlements: MyCard["entitlements"] = {
  member_id: IDS.member,
  at: "2026-10-01",
  status: "actif",
  rights_open: true,
  waiting_period_ends_on: "2026-03-01",
  plan_version_id: IDS.planVersion,
  family_annual_ceiling_xof: 3_000_000,
  consumed_xof: 420_000,
  remaining_xof: 2_580_000,
  currency: "XOF",
};

/** Carte du titulaire. `qr_*` sont recalculés à chaque appel par le mock (fenêtre de 30 s). */
export const card: MyCard = {
  card_id: IDS.cardAwa,
  person_id: IDS.awa,
  given_name: "Awa",
  family_name: "Koné",
  relationship: "titulaire",
  member_number: "MC-00928194",
  plan_code: "FAMILLE-OR",
  coverage_rate_bp: 8000,
  beneficiaries_count: 3,
  card_status: "active",
  blocked_until: null,
  qr_payload: "MC1.carte-fictive.fenetre-0000.signature-de-test",
  qr_generated_at: "2026-10-01T09:00:00Z",
  qr_refresh_at: "2026-10-01T09:00:30Z",
  entitlements,
};

export const cardKouassi: MyCard = {
  ...card,
  card_id: IDS.cardKouassi,
  person_id: IDS.kouassi,
  given_name: "Kouassi",
  relationship: "conjoint",
  member_number: "MC-00928195",
  qr_payload: "MC1.carte-fictive-conjoint.fenetre-0000.signature-de-test",
};

export const beneficiaries: MyBeneficiaryList = {
  items: [
    { person_id: IDS.awa, given_name: "Awa", family_name: "Koné", relationship: "titulaire", valid_from: "2025-01-01", valid_to: null, card_status: "active" },
    { person_id: IDS.kouassi, given_name: "Kouassi", family_name: "Koné", relationship: "conjoint", valid_from: "2025-01-01", valid_to: null, card_status: "active" },
    { person_id: IDS.aya, given_name: "Aya", family_name: "Koné", relationship: "enfant", valid_from: "2026-02-01", valid_to: null, card_status: "aucune" },
  ],
};

export const claimPharmacy: MyClaim = {
  id: IDS.claimPharmacy,
  claim_number: "PEC-26-09814",
  beneficiary_person_id: IDS.awa,
  beneficiary_given_name: "Awa",
  provider_name: "Pharmacie Riviera 3",
  service_date: "2026-09-28",
  requested_at: "2026-09-28T14:51:00Z",
  status: "accordee_auto",
  total_xof: 17_200,
  covered_xof: 13_760,
  patient_share_xof: 3_440,
  currency: "XOF",
  rule: { code: "R-12", version: 3 },
};

export const claimClinic: MyClaim = {
  id: IDS.claimClinic,
  claim_number: "PEC-26-09702",
  beneficiary_person_id: IDS.aya,
  beneficiary_given_name: "Aya",
  provider_name: "Clinique Les Palmiers",
  service_date: "2026-09-12",
  requested_at: "2026-09-12T10:05:00Z",
  status: "payee",
  total_xof: 45_000,
  covered_xof: 36_000,
  patient_share_xof: 9_000,
  currency: "XOF",
  rule: { code: "R-12", version: 3 },
};

export const claimRefused: MyClaim = {
  id: IDS.claimRefused,
  claim_number: "PEC-26-09511",
  beneficiary_person_id: IDS.kouassi,
  beneficiary_given_name: "Kouassi",
  provider_name: "Centre médical Cocody",
  service_date: "2026-08-30",
  requested_at: "2026-08-30T08:20:00Z",
  status: "refusee",
  total_xof: 62_000,
  covered_xof: 0,
  patient_share_xof: 62_000,
  currency: "XOF",
  rule: { code: "R-04", version: 2 },
};

export const claims: MyClaim[] = [claimPharmacy, claimClinic, claimRefused];

function step(key: TrackingStep["key"], state: TrackingStep["state"], at: string | null = null, patch: Partial<TrackingStep> = {}): TrackingStep {
  return { key, state, at, rule: null, reason_code: null, ...patch };
}

/** Frises calquées sur `apps/api/member_space/tracking.py` : virement et réception jamais datés (Q-P1-03). */
export const trackings: Record<string, ClaimTracking> = {
  [IDS.claimPharmacy]: {
    claim: claimPharmacy,
    steps: [
      step("demande_recue", "fait", claimPharmacy.requested_at),
      step("accordee", "fait", "2026-09-28T14:51:09Z", { rule: { code: "R-12", version: 3 }, reason_code: "R-12" }),
      step("virement", "en_cours"),
      step("recu", "a_venir"),
    ],
  },
  [IDS.claimClinic]: {
    claim: claimClinic,
    steps: [
      step("demande_recue", "fait", claimClinic.requested_at),
      step("accordee", "fait", "2026-09-12T10:05:07Z", { rule: { code: "R-12", version: 3 }, reason_code: "R-12" }),
      step("virement", "fait"),
      step("recu", "fait"),
    ],
  },
  [IDS.claimRefused]: {
    claim: claimRefused,
    steps: [
      step("demande_recue", "fait", claimRefused.requested_at),
      step("accordee", "refuse", "2026-08-30T08:20:04Z", { rule: { code: "R-04", version: 2 }, reason_code: "R-04" }),
      step("virement", "sans_objet"),
      step("recu", "sans_objet"),
    ],
  },
};

export const contributions: MyContributions = {
  items: [
    { id: IDS.octobre, period_start: "2026-10-01", due_on: "2026-10-05", amount_xof: 27_500, currency: "XOF", status: "a_payer", paid_at: null, channel: null, payer_kind: null, payer_country_code: null },
    { id: IDS.septembre, period_start: "2026-09-01", due_on: "2026-09-05", amount_xof: 27_500, currency: "XOF", status: "payee", paid_at: "2026-09-03T18:12:00Z", channel: "wave", payer_kind: "proche", payer_country_code: "FR" },
    { id: IDS.aout, period_start: "2026-08-01", due_on: "2026-08-05", amount_xof: 27_500, currency: "XOF", status: "payee", paid_at: "2026-08-04T09:40:00Z", channel: "orange_money", payer_kind: "adherent", payer_country_code: "CI" },
  ],
  next_due: null,
};
contributions.next_due = contributions.items[0] ?? null;

export const publicLink: PublicPaymentLink = {
  period_start: "2026-10-01",
  amount_xof: 27_500,
  currency: "XOF",
  holder_initials: "A. K.",
  channels: ["wave", "orange_money"],
};
