import type { ErrorCode, OfflineAuthorizationInput, OfflinePolicy } from "@/api/types";

/**
 * IndexedDB du comptoir. Contient : l'appareil (clé privée non exportable), la politique hors
 * ligne (seuil, durée, barème) et la file des accords provisoires. Jamais de nom, de photo ni
 * de donnée médicale : seulement le numéro d'adhérent et l'identifiant pseudonyme du bénéficiaire.
 */
export interface DeviceRecord {
  key: "current";
  id: string;
  privateKey: CryptoKey;
  publicJwk: string;
  registeredAt: string;
}

export interface PolicyRecord {
  key: "current";
  policy: OfflinePolicy;
  fetchedAt: string;
}

export type QueueStatus = "en_attente" | "confirmee" | "rejetee";

export interface QueueRecord {
  offline_ref: string;
  input: OfflineAuthorizationInput;
  status: QueueStatus;
  reason_code: ErrorCode | null;
  claim_id: string | null;
  authorization_id: string | null;
  created_at: string;
  synced_at: string | null;
}

interface StoreMap {
  device: DeviceRecord;
  policy: PolicyRecord;
  queue: QueueRecord;
}
export type StoreName = keyof StoreMap;

const VERSION = 1;

function promisify<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB"));
  });
}

export class CounterDb {
  constructor(private readonly db: IDBDatabase) {}

  private store<N extends StoreName>(name: N, mode: IDBTransactionMode): IDBObjectStore {
    return this.db.transaction(name, mode).objectStore(name);
  }

  async get<N extends StoreName>(name: N, key: string): Promise<StoreMap[N] | undefined> {
    return (await promisify(this.store(name, "readonly").get(key))) as StoreMap[N] | undefined;
  }

  async put<N extends StoreName>(name: N, value: StoreMap[N]): Promise<void> {
    await promisify(this.store(name, "readwrite").put(value));
  }

  async all<N extends StoreName>(name: N): Promise<StoreMap[N][]> {
    return (await promisify(this.store(name, "readonly").getAll())) as StoreMap[N][];
  }

  async delete(name: StoreName, key: string): Promise<void> {
    await promisify(this.store(name, "readwrite").delete(key));
  }

  close(): void {
    this.db.close();
  }
}

export const DB_NAME = "mulemacare-comptoir";

export function openCounterDb(name: string = DB_NAME): Promise<CounterDb> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("device")) db.createObjectStore("device", { keyPath: "key" });
      if (!db.objectStoreNames.contains("policy")) db.createObjectStore("policy", { keyPath: "key" });
      if (!db.objectStoreNames.contains("queue")) db.createObjectStore("queue", { keyPath: "offline_ref" });
    };
    request.onsuccess = () => resolve(new CounterDb(request.result));
    request.onerror = () => reject(request.error ?? new Error("IndexedDB"));
  });
}
