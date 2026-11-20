import { describe, expect, it } from "vitest";
import { card, cardKouassi } from "@/test/fixtures";
import { clearLastCard, LAST_CARD_KEY, MAX_SAVED_CARD_AGE_MS, readLastCard, saveLastCard, type KeyValueStore, type LastCardRead } from "./last-card";

function memoryStore(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

const SAVED_AT = new Date("2026-10-01T09:00:05Z");
const HOUR = 60 * 60_000;

function fresh(read: LastCardRead) {
  return read.kind === "fresh" ? read.snapshot : null;
}

describe("dernière carte lisible hors ligne", () => {
  it("garde la carte sans son QR : un QR périmé ne doit jamais être présenté", () => {
    const store = memoryStore();
    saveLastCard(store, card, null, SAVED_AT);
    const raw = store.data.get(LAST_CARD_KEY) ?? "";
    expect(raw).not.toContain(card.qr_payload);
    expect(raw).not.toContain("qr_");
    const snapshot = fresh(readLastCard(store, null, SAVED_AT.getTime() + 60_000));
    expect(snapshot?.savedAt).toBe("2026-10-01T09:00:05.000Z");
    expect(snapshot?.card.member_number).toBe("MC-00928194");
    expect(snapshot?.card.entitlements.remaining_xof).toBe(2_580_000);
    expect(snapshot?.card).not.toHaveProperty("qr_payload");
  });

  it("ne rend la carte que pour la personne demandée", () => {
    const store = memoryStore();
    const now = Date.now();
    saveLastCard(store, cardKouassi, cardKouassi.person_id, new Date(now));
    expect(readLastCard(store, null, now).kind).toBe("none");
    expect(readLastCard(store, card.person_id, now).kind).toBe("none");
    expect(fresh(readLastCard(store, cardKouassi.person_id, now))?.card.given_name).toBe("Kouassi");
  });

  it("contenu illisible ou incomplet : rien plutôt qu'une carte fausse", () => {
    const store = memoryStore();
    store.setItem(LAST_CARD_KEY, "{pas du json");
    expect(readLastCard(store, null, Date.now()).kind).toBe("none");
    // Date de lecture récente : seul le contenu incomplet doit être en cause (pas l'âge).
    store.setItem(LAST_CARD_KEY, JSON.stringify({ v: 1, personKey: "self", savedAt: new Date().toISOString(), card: { given_name: "X" } }));
    expect(readLastCard(store, null, Date.now()).kind).toBe("none");
  });

  it("stockage indisponible (navigation privée) : aucune exception", () => {
    const broken: KeyValueStore = {
      getItem: () => {
        throw new Error("refusé");
      },
      setItem: () => {
        throw new Error("plein");
      },
      removeItem: () => {
        throw new Error("refusé");
      },
    };
    expect(() => saveLastCard(broken, card, null, new Date())).not.toThrow();
    expect(readLastCard(broken, null, Date.now()).kind).toBe("none");
    expect(() => clearLastCard(broken)).not.toThrow();
  });
});

describe("durée de vie de la carte enregistrée (24 h par défaut, QUESTIONS.md Q-P1W-11)", () => {
  it("le défaut est de 24 heures", () => {
    expect(MAX_SAVED_CARD_AGE_MS).toBe(24 * HOUR);
  });

  it("jusqu'à 24 h : affichable ; au-delà : trop ancienne, effacée, plus aucune donnée lisible", () => {
    const store = memoryStore();
    saveLastCard(store, card, null, SAVED_AT);
    expect(readLastCard(store, null, SAVED_AT.getTime() + 24 * HOUR).kind).toBe("fresh");

    const late = readLastCard(store, null, SAVED_AT.getTime() + 24 * HOUR + 1);
    expect(late).toEqual({ kind: "stale", savedAt: "2026-10-01T09:00:05.000Z" });
    expect(JSON.stringify(late)).not.toContain(card.member_number);
    expect(JSON.stringify(late)).not.toContain(card.given_name);
    expect(store.data.has(LAST_CARD_KEY)).toBe(false);
    expect(readLastCard(store, null, SAVED_AT.getTime()).kind).toBe("none");
  });

  it("date d'enregistrement dans le futur (horloge reculée) : traitée comme trop ancienne", () => {
    const store = memoryStore();
    saveLastCard(store, card, null, SAVED_AT);
    expect(readLastCard(store, null, SAVED_AT.getTime() - 2 * HOUR).kind).toBe("stale");
    expect(store.data.has(LAST_CARD_KEY)).toBe(false);
  });

  it("âge maximal paramétrable", () => {
    const store = memoryStore();
    saveLastCard(store, card, null, SAVED_AT);
    expect(readLastCard(store, null, SAVED_AT.getTime() + 2 * HOUR, HOUR).kind).toBe("stale");
  });

  it("clearLastCard efface la carte", () => {
    const store = memoryStore();
    saveLastCard(store, card, null, SAVED_AT);
    clearLastCard(store);
    expect(store.data.size).toBe(0);
  });
});
