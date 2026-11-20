import { isAccessDenied, isOfflineError } from "@/api/errors";
import { isTooOld, type CardSnapshot, type LastCardRead } from "./last-card";

/** Ce que l'écran « Ma carte » peut montrer. */
export type CardChoice = { kind: "live" } | { kind: "saved"; snapshot: CardSnapshot } | { kind: "too-old"; savedAt: string } | { kind: "none" };

/**
 * Règle d'affichage de la carte :
 * - refus d'accès (session expirée, carte révoquée, 401/403/404) : RIEN, même la carte en direct
 *   gardée en mémoire par la requête précédente ; l'erreur est affichée avec son code ;
 * - réponse du serveur : la carte en direct ;
 * - erreur RÉSEAU seulement (hors ligne, serveur injoignable, délai) : la dernière carte
 *   enregistrée si elle a moins de 24 h, sinon un message « trop ancienne » sans la carte ;
 * - toute autre erreur : l'erreur.
 */
export function chooseCard({ hasData, error, saved, now }: { hasData: boolean; error: unknown; saved: LastCardRead; now: number | null }): CardChoice {
  if (isAccessDenied(error)) return { kind: "none" };
  if (hasData) return { kind: "live" };
  if (!error || !isOfflineError(error)) return { kind: "none" };
  if (saved.kind === "stale") return { kind: "too-old", savedAt: saved.savedAt };
  if (saved.kind === "fresh") {
    if (now !== null && isTooOld(saved.snapshot.savedAt, now)) return { kind: "too-old", savedAt: saved.snapshot.savedAt };
    return { kind: "saved", snapshot: saved.snapshot };
  }
  return { kind: "none" };
}
