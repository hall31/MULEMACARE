import type { MyCard } from "@/api/types";

/**
 * Calendrier du QR rotatif (Q-P1-04, Q-L4-05).
 *
 * Le serveur renvoie `qr_generated_at` et `qr_refresh_at` (début de la fenêtre suivante, 30 s).
 * On n'utilise que leur DIFFÉRENCE, appliquée à l'heure de réception sur le téléphone : une
 * horloge de téléphone fausse ne change rien.
 *
 * - `refreshAt` : on redemande le QR (même instant que `qr_refresh_at` côté serveur).
 * - `expiresAt` : au-delà, le QR affiché n'est plus présenté (bascule « expiré »). La marge
 *   `QR_GRACE_MS` (10 s) reste dans la fenêtre de tolérance du serveur (une fenêtre de 30 s) :
 *   le QR est donc toujours renouvelé AVANT que le comptoir ne le refuse.
 */
export const QR_GRACE_MS = 10_000;
/** Jamais un QR présenté plus d'une minute, même si le serveur annonçait davantage. */
export const QR_MAX_LIFETIME_MS = 60_000;

export interface QrTiming {
  receivedAt: number;
  lifetimeMs: number;
  refreshAt: number;
  expiresAt: number;
}

export type QrPhase = "valide" | "a_renouveler" | "expire";

export function qrTiming(card: Pick<MyCard, "qr_generated_at" | "qr_refresh_at">, receivedAt: number): QrTiming {
  const announced = Date.parse(card.qr_refresh_at) - Date.parse(card.qr_generated_at);
  const lifetimeMs = Number.isFinite(announced) && announced > 0 ? Math.min(announced, QR_MAX_LIFETIME_MS) : 0;
  const refreshAt = receivedAt + lifetimeMs;
  return { receivedAt, lifetimeMs, refreshAt, expiresAt: refreshAt + QR_GRACE_MS };
}

export function qrPhase(timing: QrTiming, now: number): QrPhase {
  if (now >= timing.expiresAt) return "expire";
  if (now >= timing.refreshAt) return "a_renouveler";
  return "valide";
}

/** Délai avant la prochaine demande de QR (au moins 1 s : pas de boucle serrée). */
export function msUntilRefresh(timing: QrTiming, now: number): number {
  return Math.max(1_000, timing.refreshAt - now);
}
