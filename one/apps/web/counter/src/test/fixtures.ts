import type { Identification, OfflinePolicy } from "@/api/types";

/** Jeu fictif (aucune donnée réelle d'adhérent). Barème et seuils : valeurs du prototype (proto). */
export const policy: OfflinePolicy = {
  threshold_xof: 50_000,
  validity_minutes: 120,
  currency: "XOF",
  rules: [
    { code: "R-12", version: 3 },
    { code: "HL-01", version: 1 },
  ],
  tariff: {
    at: "2026-10-01",
    items: [
      { act_code: "CS-GEN", label: "Consultation généraliste", amount_xof: 25_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
      { act_code: "NFS", label: "NFS (numération)", amount_xof: 8_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
      { act_code: "ECG", label: "ECG", amount_xof: 15_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
      { act_code: "ECHO-ABD", label: "Échographie abdominale", amount_xof: 30_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: false },
      { act_code: "IRM", label: "IRM", amount_xof: 45_000, currency: "XOF", valid_from: "2026-01-01", valid_to: null, requires_prior_approval: true },
      { act_code: "ANCIEN", label: "Acte retiré", amount_xof: 1_000, currency: "XOF", valid_from: "2025-01-01", valid_to: "2025-12-31", requires_prior_approval: false },
    ],
  },
};

export const verified: Identification = {
  id: "0b8f3f5e-4d1c-4a55-9d5a-2f7c1c3e9a01",
  status: "verifiee",
  qr_verified: true,
  photo_confirmed: true,
  code_verified: true,
  beneficiary: {
    person_id: "5a0e6f1c-2b7d-4e1a-8c33-7d9e0a4b6c12",
    member_number: "MC-00000042",
    display_name: "Aya Démo",
    photo_url: null,
    plan_code: "ESSENTIEL",
    coverage_rate_bp: 8000,
    member_status: "actif",
  },
};
