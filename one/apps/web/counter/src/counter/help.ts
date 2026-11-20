import type { StepName } from "./ui";

/**
 * Aide de première utilisation du comptoir (Phase 2, voie A) : une bulle sobre par écran, non
 * bloquante (rien n'est recouvert, l'action principale reste disponible), retirée par « Compris »
 * pour cet écran, désactivable d'un geste et réactivable depuis la barre du haut. Mémorisée sur
 * l'appareil : écrans déjà vus et interrupteur, jamais une donnée de patient.
 */
export const HELP_KEY = "mulema.comptoir.aide";

export const HELP_STEPS: readonly StepName[] = ["card", "identity", "code", "acts", "decision"];

export interface HelpState {
  off: boolean;
  seen: StepName[];
}

export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const FRESH: HelpState = { off: false, seen: [] };

export function readHelp(store: KeyValueStore): HelpState {
  try {
    const raw = store.getItem(HELP_KEY);
    if (!raw) return FRESH;
    const value = JSON.parse(raw) as { v?: unknown; off?: unknown; seen?: unknown };
    if (value.v !== 1) return FRESH;
    const seen = Array.isArray(value.seen) ? value.seen.filter((s): s is StepName => (HELP_STEPS as readonly unknown[]).includes(s)) : [];
    return { off: value.off === true, seen };
  } catch {
    return FRESH;
  }
}

export function writeHelp(store: KeyValueStore, state: HelpState): void {
  try {
    store.setItem(HELP_KEY, JSON.stringify({ v: 1, off: state.off, seen: state.seen }));
  } catch {
    // Stockage refusé : l'aide reviendra au prochain lancement, sans autre conséquence.
  }
}

export function shouldShowHelp(state: HelpState, step: StepName): boolean {
  return !state.off && !state.seen.includes(step);
}

export function markSeen(state: HelpState, step: StepName): HelpState {
  return state.seen.includes(step) ? state : { ...state, seen: [...state.seen, step] };
}

export function disableHelp(state: HelpState): HelpState {
  return { ...state, off: true };
}

/** Réactiver : toutes les aides reviennent, écran par écran. */
export function enableHelp(_state: HelpState): HelpState {
  return { off: false, seen: [] };
}
