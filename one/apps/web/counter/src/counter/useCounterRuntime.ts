"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { createApiClient, type ApiClient } from "@/api/client";
import type { CurrentUser, OfflinePolicy } from "@/api/types";
import { t } from "@/i18n";
import { openCounterDb, type CounterDb, type DeviceRecord, type QueueRecord } from "@/offline/db";
import { listRecords, purgeConfirmed, syncPending } from "@/offline/queue";
import { exportPublicJwk, generateDeviceKeys } from "@/offline/signing";

const DEFAULT_TIMEZONE = "Africa/Abidjan";
const TZ_STORAGE_KEY = "mulema.timezone";
const SYNC_INTERVAL_MS = 30_000;

function subscribeOnline(callback: () => void): () => void {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

export type SyncState = "idle" | "syncing" | "error";

export interface CounterRuntime {
  api: ApiClient;
  online: boolean;
  db: CounterDb | null;
  device: DeviceRecord | null;
  policy: OfflinePolicy | null;
  /** Réception de la politique sur l'appareil (fraîcheur vérifiée avant tout accord, Q-L7-06). */
  policyFetchedAt: string | null;
  me: CurrentUser | null;
  /** `/v1/me` attendu (premier chargement en ligne) : squelette dans la barre du haut. */
  meLoading: boolean;
  /** Politique hors ligne (barème) attendue alors qu'aucune n'est encore sur l'appareil. */
  policyLoading: boolean;
  /** Relance le chargement de la politique (état vide ou erreur de l'écran des actes). */
  retryPolicy: () => void;
  timeZone: string;
  queue: QueueRecord[];
  syncState: SyncState;
  refreshQueue: () => Promise<void>;
  syncNow: () => Promise<void>;
  purge: () => Promise<void>;
}

export function useCounterRuntime(): CounterRuntime {
  const api = useMemo(() => createApiClient(), []);
  const online = useOnline();
  const [db, setDb] = useState<CounterDb | null>(null);
  const [device, setDevice] = useState<DeviceRecord | null>(null);
  const [policy, setPolicy] = useState<OfflinePolicy | null>(null);
  const [policyFetchedAt, setPolicyFetchedAt] = useState<string | null>(null);
  const [queue, setQueue] = useState<QueueRecord[]>([]);
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [storedTz, setStoredTz] = useState<string | null>(null);
  const syncing = useRef(false);
  const registering = useRef(false);

  // Ouverture de la base locale et lecture de l'état persistant.
  useEffect(() => {
    let cancelled = false;
    let opened: CounterDb | null = null;
    setStoredTz(window.localStorage.getItem(TZ_STORAGE_KEY));
    void (async () => {
      const handle = await openCounterDb();
      opened = handle;
      if (cancelled) {
        handle.close();
        return;
      }
      const [storedDevice, storedPolicy] = await Promise.all([handle.get("device", "current"), handle.get("policy", "current")]);
      await purgeConfirmed(handle);
      if (cancelled) return;
      setDevice(storedDevice ?? null);
      setPolicy(storedPolicy?.policy ?? null);
      setPolicyFetchedAt(storedPolicy?.fetchedAt ?? null);
      setQueue(await listRecords(handle));
      setDb(handle);
    })();
    return () => {
      cancelled = true;
      opened?.close();
    };
  }, []);

  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => api.getCurrentUser(), enabled: online });
  const policyQuery = useQuery({ queryKey: ["offline-policy"], queryFn: () => api.getOfflinePolicy(), enabled: online && db !== null });

  const me = meQuery.data ?? null;
  useEffect(() => {
    const tz = me?.organization.timezone;
    if (tz) {
      window.localStorage.setItem(TZ_STORAGE_KEY, tz);
      setStoredTz(tz);
    }
  }, [me]);

  // Politique hors ligne : conservée sur l'appareil pour les coupures à venir.
  useEffect(() => {
    const fresh = policyQuery.data;
    if (!fresh || !db) return;
    const fetchedAt = new Date().toISOString();
    setPolicy(fresh);
    setPolicyFetchedAt(fetchedAt);
    void db.put("policy", { key: "current", policy: fresh, fetchedAt });
  }, [policyQuery.data, db]);

  // Enregistrement de l'appareil (clé publique) au premier passage en ligne.
  useEffect(() => {
    if (!online || !db || device || registering.current) return;
    registering.current = true;
    void (async () => {
      try {
        const keys = await generateDeviceKeys();
        const publicJwk = await exportPublicJwk(keys.publicKey);
        const registered = await api.registerDevice({ label: t("app.deviceLabel"), public_key: publicJwk });
        const record: DeviceRecord = { key: "current", id: registered.id, privateKey: keys.privateKey, publicJwk, registeredAt: registered.registered_at };
        await db.put("device", record);
        setDevice(record);
      } catch {
        // Nouvel essai au prochain retour en ligne.
      } finally {
        registering.current = false;
      }
    })();
  }, [online, db, device, api]);

  const refreshQueue = useCallback(async () => {
    if (db) setQueue(await listRecords(db));
  }, [db]);

  const syncNow = useCallback(async () => {
    if (!db || !device || syncing.current || !navigator.onLine) return;
    const pending = (await listRecords(db)).some((r) => r.status === "en_attente");
    if (!pending) return;
    syncing.current = true;
    setSyncState("syncing");
    try {
      await syncPending({ db, api, deviceId: device.id });
      setSyncState("idle");
    } catch {
      setSyncState("error");
    } finally {
      syncing.current = false;
      setQueue(await listRecords(db));
    }
  }, [db, device, api]);

  const purge = useCallback(async () => {
    if (!db) return;
    await purgeConfirmed(db);
    setQueue(await listRecords(db));
  }, [db]);

  // Rapprochement au retour du réseau, puis à intervalle régulier tant qu'il reste des accords.
  const hasPending = queue.some((r) => r.status === "en_attente");
  useEffect(() => {
    if (!online || !hasPending) return;
    void syncNow();
    const timer = window.setInterval(() => void syncNow(), SYNC_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [online, hasPending, syncNow]);

  const { refetch: refetchPolicy } = policyQuery;
  const retryPolicy = useCallback(() => {
    void refetchPolicy();
  }, [refetchPolicy]);

  return {
    api,
    online,
    db,
    device,
    policy,
    policyFetchedAt,
    me,
    meLoading: online && meQuery.isPending,
    policyLoading: online && policy === null && (db === null || policyQuery.isPending || policyQuery.isFetching),
    retryPolicy,
    timeZone: me?.organization.timezone ?? storedTz ?? DEFAULT_TIMEZONE,
    queue,
    syncState,
    refreshQueue,
    syncNow,
    purge,
  };
}
