import type { ClaimItemInput, Identification, OfflinePolicy, TariffItem } from "@/api/types";

/**
 * Évaluation locale d'un accord provisoire (R13). Ce n'est pas une décision métier nouvelle :
 * elle applique la politique publiée par la mutuelle (`GET /v1/counter/offline-policy`, règles
 * R-12 et HL-01) et le serveur revérifie tout à la synchronisation (OFF-01…OFF-04).
 */
export type OfflineRefusal =
  | "no_policy"
  | "stale_policy"
  | "no_device"
  | "not_verified"
  | "member_status"
  | "unknown_act"
  | "prior_approval"
  | "above_threshold";

/** Durée maximale d'un accord provisoire, quelle que soit la politique reçue (R13 : 2 h). */
export const MAX_VALIDITY_MINUTES = 120;

/**
 * Âge maximal de la politique en cache (Q-L7-06) : au-delà, le seuil et le barème ont pu changer
 * côté mutuelle, l'appareil ne signe plus d'accord provisoire. 72 h couvrent une coupure d'un
 * week-end prolongé ; la politique est rafraîchie à chaque passage en ligne.
 */
export const MAX_POLICY_AGE_HOURS = 72;

/** Politique utilisable : reçue il y a au plus MAX_POLICY_AGE_HOURS, jamais dans le futur. */
export function isPolicyFresh(fetchedAt: string | null, now: Date): boolean {
  if (!fetchedAt) return false;
  const fetched = Date.parse(fetchedAt);
  if (Number.isNaN(fetched)) return false;
  const age = now.getTime() - fetched;
  // Âge négatif : horloge de l'appareil reculée, la fraîcheur n'est plus vérifiable.
  return age >= 0 && age <= MAX_POLICY_AGE_HOURS * 3_600_000;
}

export interface OfflineQuote {
  items: ClaimItemInput[];
  total_xof: number;
  covered_xof: number;
  patient_share_xof: number;
}

export type OfflineEvaluation =
  | { allowed: true; quote: OfflineQuote; issuedAt: string; expiresAt: string; policy: OfflinePolicy }
  | { allowed: false; reason: OfflineRefusal; quote?: OfflineQuote };

export interface OfflineEvaluationInput {
  policy: OfflinePolicy | null;
  /** Date de réception de la politique sur l'appareil (PolicyRecord.fetchedAt). */
  policyFetchedAt: string | null;
  deviceId: string | null;
  identification: Identification | null;
  selectedActs: readonly string[];
  serviceDate: string;
  now: Date;
}

/** Actes du barème en vigueur à la date du soin (dates AAAA-MM-JJ, comparables en texte). */
export function tariffAt(policy: OfflinePolicy, serviceDate: string): TariffItem[] {
  return policy.tariff.items.filter(
    (item) => item.valid_from <= serviceDate && (item.valid_to == null || serviceDate <= item.valid_to),
  );
}

/** Part mutuelle en entiers FCFA : taux en points de base, arrondi au franc le plus proche (proto). */
export function coveredAmount(totalXof: number, rateBp: number): number {
  return Math.floor((totalXof * rateBp + 5_000) / 10_000);
}

export function evaluateOffline(input: OfflineEvaluationInput): OfflineEvaluation {
  const { policy, policyFetchedAt, deviceId, identification, selectedActs, serviceDate, now } = input;
  if (!policy) return { allowed: false, reason: "no_policy" };
  if (!isPolicyFresh(policyFetchedAt, now)) return { allowed: false, reason: "stale_policy" };
  if (!deviceId) return { allowed: false, reason: "no_device" };
  if (!identification || identification.status !== "verifiee" || !identification.code_verified) {
    return { allowed: false, reason: "not_verified" };
  }
  if (identification.beneficiary.member_status !== "actif") return { allowed: false, reason: "member_status" };

  const tariff = new Map(tariffAt(policy, serviceDate).map((item) => [item.act_code, item]));
  if (selectedActs.length === 0) return { allowed: false, reason: "unknown_act" };
  const lines: TariffItem[] = [];
  for (const code of selectedActs) {
    const item = tariff.get(code);
    if (!item) return { allowed: false, reason: "unknown_act" };
    lines.push(item);
  }

  const total = lines.reduce((sum, item) => sum + item.amount_xof, 0);
  const covered = coveredAmount(total, identification.beneficiary.coverage_rate_bp);
  const quote: OfflineQuote = {
    items: lines.map((item) => ({ act_code: item.act_code, quantity: 1 })),
    total_xof: total,
    covered_xof: covered,
    patient_share_xof: total - covered,
  };
  if (lines.some((item) => item.requires_prior_approval)) return { allowed: false, reason: "prior_approval", quote };
  // Borne exclue (Q-L0-02) : au seuil exact, c'est la revue du médecin-conseil.
  if (total >= policy.threshold_xof) return { allowed: false, reason: "above_threshold", quote };

  const minutes = Math.min(policy.validity_minutes, MAX_VALIDITY_MINUTES);
  const expires = new Date(now.getTime() + minutes * 60_000);
  return { allowed: true, quote, issuedAt: now.toISOString(), expiresAt: expires.toISOString(), policy };
}
