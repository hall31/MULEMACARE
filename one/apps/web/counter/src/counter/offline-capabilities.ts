import type { MessageKey, MessageParams } from "@/i18n";
import { MAX_VALIDITY_MINUTES } from "@/offline/policy";

/**
 * Bandeau hors ligne du comptoir (contrat de design §8) : ce qui reste possible et ce qui ne l'est
 * pas, selon l'étape (identification faite ou non) et la politique hors ligne de l'appareil. Les
 * règles elles-mêmes sont celles de `src/offline/policy.ts` (R13, Q-L7-01, Q-L7-06) : ce module ne
 * fait que les dire.
 */
export interface CapabilityLine {
  key: MessageKey;
  params?: MessageParams;
}

export interface OfflineCapabilities {
  can: CapabilityLine[];
  cannot: CapabilityLine[];
}

export interface CapabilityInput {
  identified: boolean;
  /** Politique reçue, à jour, et appareil enregistré : un accord provisoire peut être signé. */
  canSign: boolean;
  thresholdXof: number | null;
  validityMinutes: number | null;
}

/** « 2 h », « 1 h 30 », « 45 min » : durée de validité plafonnée comme dans la politique. */
export function formatDuration(minutes: number): string {
  const capped = Math.max(0, Math.min(minutes, MAX_VALIDITY_MINUTES));
  const h = Math.floor(capped / 60);
  const m = capped % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, "0")}`;
}

export function offlineCapabilities({ identified, canSign, thresholdXof, validityMinutes }: CapabilityInput): OfflineCapabilities {
  const identify: CapabilityLine = { key: "net.cannot.identify" };
  if (!identified) return { can: [{ key: "net.can.finish" }], cannot: [identify] };
  if (canSign && thresholdXof !== null && validityMinutes !== null) {
    return {
      can: [{ key: "net.can.provisional", params: { threshold: thresholdXof, duration: formatDuration(validityMinutes) } }, { key: "net.can.sync" }],
      cannot: [{ key: "net.cannot.above", params: { threshold: thresholdXof } }, identify],
    };
  }
  return { can: [{ key: "net.can.retry" }], cannot: [{ key: "net.cannot.provisional" }, identify] };
}
