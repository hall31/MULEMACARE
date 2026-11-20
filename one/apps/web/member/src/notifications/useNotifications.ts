"use client";

import { useCallback, useEffect, useMemo, useSyncExternalStore } from "react";
import { browserStore } from "@/card/last-card";
import { useBeneficiaries, useClaims, useContributions, useTimeZone, type SharedReadOptions } from "@/member/queries";
import {
  DEFAULT_PREFS,
  NOTIFICATIONS_KEY,
  acknowledge,
  baselineOf,
  deriveNotifications,
  localDay,
  markRead,
  migrateNotificationState,
  readNotificationState,
  unreadCount,
  writeNotificationState,
  type AppNotification,
  type NotificationState,
} from "./derive";

/* ------------------------------------------------ état local partagé (cloche + écran) ------------------------------------------------ */

const CHANGE_EVENT = "mulema:notifications";
const SERVER_STATE: NotificationState = { prefs: DEFAULT_PREFS, baseline: null, read: [] };
let cached: { raw: string | null; state: NotificationState } | null = null;

function snapshot(): NotificationState {
  const store = browserStore();
  let raw: string | null = null;
  try {
    raw = store?.getItem(NOTIFICATIONS_KEY) ?? null;
  } catch {
    raw = null;
  }
  if (cached && cached.raw === raw) return cached.state;
  const state = store ? readNotificationState(store) : SERVER_STATE;
  cached = { raw, state };
  return state;
}

function subscribe(callback: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === NOTIFICATIONS_KEY) callback();
  };
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(CHANGE_EVENT, callback);
    window.removeEventListener("storage", onStorage);
  };
}

export function useNotificationState(): [NotificationState, (next: NotificationState) => void] {
  // Un état d'une version antérieure (identifiants et statuts en clair) est réécrit en empreintes.
  useEffect(() => {
    const store = browserStore();
    if (store) migrateNotificationState(store);
  }, []);
  const state = useSyncExternalStore(subscribe, snapshot, () => SERVER_STATE);
  const set = useCallback((next: NotificationState) => {
    const store = browserStore();
    if (store) writeNotificationState(store, next);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);
  return [state, set];
}

/* ------------------------------------------------ notifications dérivées ------------------------------------------------ */

export interface NotificationsView {
  list: AppNotification[];
  unread: number;
  state: NotificationState;
  setState: (next: NotificationState) => void;
  markAllRead: () => void;
  markRead: (key: string) => void;
  /** Au moins une source a des données (affichables, même hors ligne). */
  ready: boolean;
  pending: boolean;
  /** Toutes les sources ont échoué sans aucune donnée. */
  failed: boolean;
  /** Une source a échoué alors que d'autres ont répondu : liste peut-être incomplète. */
  partialError: unknown;
  firstError: unknown;
  retry: () => void;
  retrying: boolean;
}

/**
 * Notifications dérivées des trois lectures du contrat déjà utilisées par l'espace (mêmes clés de
 * requête : aucun appel en plus quand l'écran les a déjà chargées). La première lecture des
 * dossiers pose la référence silencieusement : rien n'est signalé « nouveau » à la toute première
 * ouverture.
 */
export function useNotifications(options: SharedReadOptions = {}): NotificationsView {
  const contributions = useContributions(options);
  const claims = useClaims(options);
  const beneficiaries = useBeneficiaries(options);
  const timeZone = useTimeZone();
  const [state, setState] = useNotificationState();
  const claimList = claims.data?.pages[0]?.items;

  useEffect(() => {
    // État relu sur le téléphone, pas celui du rendu : un composant hydraté après l'arrivée des
    // données voit encore l'instantané serveur (sans référence) et aurait écrasé la référence, les
    // lectures et les préférences enregistrées.
    const stored = snapshot();
    if (state.baseline === null && stored.baseline === null && claimList) setState({ ...stored, baseline: baselineOf(claimList) });
  }, [state, claimList, setState]);

  const list = useMemo(
    () =>
      deriveNotifications({
        today: localDay(new Date(), timeZone),
        contributions: contributions.data,
        claims: claimList,
        beneficiaries: beneficiaries.data?.items,
        state,
      }),
    [contributions.data, claimList, beneficiaries.data, state, timeZone],
  );

  const sources = [contributions, claims, beneficiaries];
  const withData = sources.filter((q) => q.data !== undefined).length;
  const errors = sources.filter((q) => q.isError);
  return {
    list,
    unread: unreadCount(list),
    state,
    setState,
    markAllRead: () => setState(acknowledge(state, list, claimList ?? [])),
    markRead: (key) => setState(markRead(state, key)),
    ready: withData > 0,
    pending: sources.some((q) => q.isPending) && withData === 0 && errors.length === 0,
    failed: withData === 0 && errors.length > 0 && !sources.some((q) => q.isPending),
    partialError: withData > 0 ? errors[0]?.error : undefined,
    firstError: errors[0]?.error,
    retry: () => {
      for (const q of sources) if (q.isError) void q.refetch();
    },
    retrying: sources.some((q) => q.isFetching),
  };
}
