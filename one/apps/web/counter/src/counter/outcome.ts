import type { ClaimCreated } from "@/api/types";
import type { QueueRecord } from "@/offline/db";
import type { OfflineQuote, OfflineRefusal } from "@/offline/policy";

export type Outcome =
  | { kind: "online"; created: ClaimCreated }
  | { kind: "provisional"; offlineRef: string; quote: OfflineQuote; expiresAt: string }
  | { kind: "offline_refused"; reason: OfflineRefusal; quote?: OfflineQuote };

export function recordFor(queue: readonly QueueRecord[], ref: string): QueueRecord | undefined {
  return queue.find((record) => record.offline_ref === ref);
}
