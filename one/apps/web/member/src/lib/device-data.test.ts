import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { LAST_CARD_KEY, saveLastCard } from "@/card/last-card";
import { NOTIFICATIONS_KEY } from "@/notifications/derive";
import { TOUR_KEY } from "@/onboarding/tour";
import { MEASURE_CHOICE_KEY } from "./measure-consent";
import { TELEMETRY_KEY } from "./telemetry";
import { card } from "@/test/fixtures";
import { PERSISTED_KEYS, STORAGE_PREFIX, purgeDeviceData, type CacheStore, type ScannableStore } from "./device-data";

function memoryStore(initial: Record<string, string> = {}): ScannableStore & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial));
  return {
    data,
    get length() {
      return data.size;
    },
    key: (i) => [...data.keys()][i] ?? null,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

function memoryCaches(names: string[]): CacheStore & { names: Set<string> } {
  const set = new Set(names);
  return {
    names: set,
    keys: async () => [...set],
    delete: async (name) => set.delete(name),
  };
}

describe("déconnexion : rien de l'adhérent ne reste sur le téléphone", () => {
  it("inventaire : dernière carte, découverte et notifications, toutes sous le préfixe de l'espace", () => {
    expect(PERSISTED_KEYS).toEqual([LAST_CARD_KEY, TOUR_KEY, NOTIFICATIONS_KEY, TELEMETRY_KEY]);
    // Le choix de mesure n'est pas une donnée de l'adhérent : il survit à la déconnexion.
    expect(PERSISTED_KEYS).not.toContain(MEASURE_CHOICE_KEY);
    for (const key of PERSISTED_KEYS) expect(key.startsWith(STORAGE_PREFIX)).toBe(true);
  });

  it("efface la carte enregistrée, toute clé de l'espace, les caches du service worker et la mémoire des requêtes", async () => {
    const store = memoryStore({ [`${STORAGE_PREFIX}future`]: "x", "autre.application": "garde" });
    saveLastCard(store, card, null, new Date());
    const caches = memoryCaches(["adherent-v1", "adherent-v0"]);
    const queryClient = new QueryClient();
    queryClient.setQueryData(["card", "self"], card);
    queryClient.setQueryData(["me"], { id: "u" });

    await purgeDeviceData({ store, caches, queryClient });

    expect([...store.data.keys()]).toEqual(["autre.application"]);
    expect(caches.names.size).toBe(0);
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
  });

  it("stockage ou caches indisponibles : la purge va au bout sans exception", async () => {
    const refused: ScannableStore = {
      length: 1,
      key: () => {
        throw new Error("refusé");
      },
      getItem: () => null,
      setItem: () => undefined,
      removeItem: () => {
        throw new Error("refusé");
      },
    };
    const brokenCaches: CacheStore = {
      keys: async () => {
        throw new Error("refusé");
      },
      delete: async () => false,
    };
    const queryClient = new QueryClient();
    queryClient.setQueryData(["card", "self"], card);
    await expect(purgeDeviceData({ store: refused, caches: brokenCaches, queryClient })).resolves.toBeUndefined();
    await expect(purgeDeviceData({ store: null, caches: null, queryClient })).resolves.toBeUndefined();
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
  });
});
