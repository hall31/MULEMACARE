import type { SyncState } from "./useCounterRuntime";

/**
 * Tons des statuts (AGENTS.md, Design ; contrat §5) : couleurs sémantiques uniquement, jamais
 * l'accent. Accordé → ok ; en revue, hors ligne → warn ; refusé → crit ; en cours → info.
 */
export type StatusTone = "ok" | "warn" | "crit" | "info";

/** Classes de `globals.css` : fond et texte du ton (`.tone-*`), filet latéral sur `.alert`. */
export const STATUS_TONE_CLASSES: Record<StatusTone, string> = {
  ok: "tone-ok",
  warn: "tone-warn",
  crit: "tone-crit",
  info: "tone-info",
};

/** Accords en attente ou en cours d'envoi : à surveiller ; échec d'envoi : critique. */
export const SYNC_TONE: Record<SyncState, StatusTone> = {
  idle: "warn",
  syncing: "warn",
  error: "crit",
};
