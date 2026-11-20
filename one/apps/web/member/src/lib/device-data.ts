import type { QueryClient } from "@tanstack/react-query";
import { LAST_CARD_KEY, type KeyValueStore } from "@/card/last-card";
import { NOTIFICATIONS_KEY } from "@/notifications/derive";
import { TOUR_KEY } from "@/onboarding/tour";
import { TELEMETRY_KEY } from "./telemetry";

/**
 * Inventaire de ce que l'espace adhérent garde sur le téléphone (QUESTIONS.md « Stockage sur le
 * téléphone ») : la dernière carte, l'état du parcours de découverte, les préférences et la
 * dernière lecture des notifications, l'interrupteur de la mesure produit. Toute clé doit vivre sous `STORAGE_PREFIX` pour être effacée
 * à la déconnexion.
 */
export const STORAGE_PREFIX = "mulema.adherent.";
export const PERSISTED_KEYS = [LAST_CARD_KEY, TOUR_KEY, NOTIFICATIONS_KEY, TELEMETRY_KEY] as const;

/** localStorage, parcourable pour effacer toute clé de l'espace. */
export interface ScannableStore extends KeyValueStore {
  readonly length: number;
  key(index: number): string | null;
}

/** Cache Storage du service worker (coquille de l'application). */
export type CacheStore = Pick<CacheStorage, "keys" | "delete">;

function keysToRemove(store: ScannableStore): string[] {
  const keys = new Set<string>(PERSISTED_KEYS);
  try {
    for (let i = 0; i < store.length; i += 1) {
      const key = store.key(i);
      if (key?.startsWith(STORAGE_PREFIX)) keys.add(key);
    }
  } catch {
    // Parcours refusé : on efface au moins les clés connues.
  }
  return [...keys];
}

/**
 * Déconnexion : efface la mémoire des requêtes (requêtes en cours annulées : une réponse tardive
 * ne réécrit pas la carte), la carte enregistrée et toute clé de l'espace, puis les caches du
 * service worker. Ne lève jamais : chaque étape va au bout même si une autre est refusée.
 */
export async function purgeDeviceData({ store, caches, queryClient }: { store: ScannableStore | null; caches: CacheStore | null; queryClient: QueryClient }): Promise<void> {
  await queryClient.cancelQueries();
  queryClient.clear();
  if (store) {
    for (const key of keysToRemove(store)) {
      try {
        store.removeItem(key);
      } catch {
        // Stockage refusé : rien n'a pu y être écrit.
      }
    }
  }
  if (caches) {
    try {
      const names = await caches.keys();
      await Promise.all(names.map((name) => caches.delete(name)));
    } catch {
      // Cache Storage indisponible (contexte non sécurisé) : le service worker n'a rien pu y mettre.
    }
  }
}

/** Stockages du navigateur, ou rien (rendu serveur, stockage interdit). */
export function browserDeviceStores(): { store: ScannableStore | null; caches: CacheStore | null } {
  if (typeof window === "undefined") return { store: null, caches: null };
  let store: ScannableStore | null = null;
  try {
    store = window.localStorage;
  } catch {
    store = null;
  }
  return { store, caches: "caches" in window ? window.caches : null };
}
