import type { EventProps, ProductEventName } from "./telemetry";

/**
 * Point d'entrée léger de la mesure produit pour les écrans du premier affichage (coquille, carte) :
 * le client complet (`./telemetry.ts` : liste blanche, consentement, envoi) est chargé à part, hors
 * du JavaScript initial de la carte (PERFORMANCE.md), et préchargé après le premier affichage pour
 * être en cache (service worker) avant une coupure. S'il n'a pas encore pu être chargé, les
 * événements attendent en mémoire (20 au plus) et partent au retour du réseau ; le client applique
 * ensuite ses propres règles (consentement d'abord, rien hors liste blanche).
 */
type Load = () => Promise<{ track: (name: ProductEventName, props?: EventProps) => void }>;

const MAX_PENDING = 20;

export function createTracker(load: Load) {
  const pending: Array<[ProductEventName, EventProps | undefined]> = [];
  let loading: ReturnType<Load> | null = null;

  const client = (): ReturnType<Load> => {
    loading ??= load().catch((error: unknown) => {
      loading = null;
      throw error;
    });
    return loading;
  };

  const drain = (): void => {
    if (pending.length === 0) return;
    client()
      .then((telemetry) => {
        for (const [name, props] of pending.splice(0)) telemetry.track(name, props);
      })
      .catch(() => undefined);
  };

  return {
    track(name: ProductEventName, props?: EventProps): void {
      if (pending.length < MAX_PENDING) pending.push([name, props]);
      drain();
    },
    drain,
    preload(): void {
      client().catch(() => undefined);
    },
  };
}

const tracker = createTracker(() => import("./telemetry"));
if (typeof window !== "undefined") window.addEventListener("online", tracker.drain);

export const track = (name: ProductEventName, props?: EventProps): void => {
  if (typeof window !== "undefined") tracker.track(name, props);
};

export const preloadTelemetry = (): void => {
  if (typeof window !== "undefined") tracker.preload();
};
