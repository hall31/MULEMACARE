"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useEffect, useState, useSyncExternalStore } from "react";
import { api } from "@/api/client";
import type { MyCard } from "@/api/types";
import { browserStore, saveLastCard } from "@/card/last-card";
import { msUntilRefresh, qrTiming } from "@/card/qr-schedule";

/** Les deux fuseaux de l'instance (Abidjan, Dakar) sont UTC+0 sans heure d'été : repli sûr avant /v1/me. */
export const DEFAULT_TIME_ZONE = "Africa/Abidjan";

export const queryKeys = {
  me: ["me"] as const,
  card: (personId: string | null) => ["card", personId ?? "self"] as const,
  beneficiaries: ["beneficiaries"] as const,
  claims: ["claims"] as const,
  tracking: (claimId: string) => ["tracking", claimId] as const,
  contributions: ["contributions"] as const,
  publicLink: (token: string) => ["public-link", token] as const,
};

export function useMe() {
  return useQuery({ queryKey: queryKeys.me, queryFn: () => api.getCurrentUser(), staleTime: 10 * 60_000 });
}

export function useTimeZone(): string {
  return useMe().data?.organization.timezone ?? DEFAULT_TIME_ZONE;
}

/** Hors ligne pendant une panne : nouvel essai toutes les 5 s (le retour du réseau relance aussi). */
const RETRY_WHILE_FAILING_MS = 5_000;

/**
 * Carte et QR rotatif : redemandé à l'échéance annoncée par le serveur (Q-P1-04), jamais mis en
 * cache HTTP (`no-store`) ; la dernière carte lue est gardée sans son QR pour le hors ligne.
 */
export function useMyCard(personId: string | null) {
  return useQuery({
    queryKey: queryKeys.card(personId),
    queryFn: async ({ signal }): Promise<MyCard> => {
      const card = await api.getMyCard(personId ?? undefined);
      // Requête annulée (déconnexion pendant l'appel) : la réponse tardive n'est pas enregistrée.
      const store = browserStore();
      if (store && !signal.aborted) saveLastCard(store, card, personId, new Date());
      return card;
    },
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    refetchIntervalInBackground: false,
    refetchInterval: (query) => {
      const { data, dataUpdatedAt, fetchFailureCount, status } = query.state;
      if (status === "error" || fetchFailureCount > 0) return RETRY_WHILE_FAILING_MS;
      return data ? msUntilRefresh(qrTiming(data, dataUpdatedAt), Date.now()) : false;
    },
  });
}

/**
 * Lecture partagée par un écran et un observateur monté plus tard (compteur de la cloche, chargé à
 * part) : `retryOnMount: false` pour l'observateur, qui ne relance pas une lecture en erreur ; sinon
 * l'erreur affichée par l'écran (code, « Réessayer ») disparaîtrait d'elle-même.
 */
export interface SharedReadOptions {
  retryOnMount?: boolean;
}

export function useBeneficiaries(options: SharedReadOptions = {}) {
  return useQuery({ queryKey: queryKeys.beneficiaries, queryFn: () => api.listMyBeneficiaries(), ...options });
}

export function useClaims(options: SharedReadOptions = {}) {
  return useInfiniteQuery({
    ...options,
    queryKey: queryKeys.claims,
    queryFn: ({ pageParam }) => api.listMyClaims(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.page.next_cursor ?? undefined,
  });
}

export function useTracking(claimId: string | null) {
  return useQuery({
    queryKey: queryKeys.tracking(claimId ?? ""),
    queryFn: () => api.getMyClaimTracking(claimId ?? ""),
    enabled: claimId !== null,
  });
}

export function useContributions(options: SharedReadOptions = {}) {
  return useQuery({ queryKey: queryKeys.contributions, queryFn: () => api.listMyContributions(), ...options });
}

/* ------------------------------------------------ réseau et horloge ------------------------------------------------ */

function subscribeOnline(callback: () => void): () => void {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

/** État du réseau vu par le navigateur ; « en ligne » au rendu serveur. */
export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

/** Heure courante, rafraîchie à intervalle (compte à rebours du QR). Nulle au rendu serveur. */
export function useNow(intervalMs = 1_000): number | null {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);
  return now;
}
