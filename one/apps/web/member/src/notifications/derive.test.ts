import { describe, expect, it } from "vitest";
import type { MyBeneficiary, MyClaim, MyContribution } from "@/api/types";
import { STORAGE_PREFIX } from "@/lib/device-data";
import { beneficiaries, claimClinic, claimPharmacy, claimRefused, contributions } from "@/test/fixtures";
import {
  DEFAULT_PREFS,
  NOTIFICATIONS_KEY,
  acknowledge,
  baselineOf,
  deriveNotifications,
  markRead,
  migrateNotificationState,
  readNotificationState,
  unreadCount,
  writeNotificationState,
  type NotificationState,
} from "./derive";

const TODAY = "2026-10-01";
const october = contributions.items[0]!;

function memoryStore(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    data,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

const baseline = (claims: MyClaim[]): NotificationState => ({ prefs: DEFAULT_PREFS, baseline: baselineOf(claims), read: [] });

function derive(over: Partial<Parameters<typeof deriveNotifications>[0]> = {}) {
  return deriveNotifications({
    today: TODAY,
    contributions: { items: [october], next_due: october },
    claims: [claimPharmacy, claimClinic, claimRefused],
    beneficiaries: beneficiaries.items,
    state: baseline([claimPharmacy, claimClinic, claimRefused]),
    ...over,
  });
}

describe("échéance de cotisation", () => {
  it("échéance dans le délai d'alerte (7 jours par défaut) : notification « à payer », ton attention", () => {
    const list = derive();
    const due = list.find((n) => n.kind === "contribution-due");
    expect(due).toMatchObject({ key: `contribution:${october.id}:a_payer`, tone: "warn", href: "/cotisations", unread: true });
    expect(due?.params).toMatchObject({ date: "05/10/2026", days: 4 });
  });

  it("échéance plus lointaine que le délai : rien ; délai réglé à 14 jours : notifiée", () => {
    const far: MyContribution = { ...october, due_on: "2026-10-12" };
    expect(derive({ contributions: { items: [far], next_due: far } }).filter((n) => n.kind === "contribution-due")).toEqual([]);
    const state = { ...baseline([]), prefs: { ...DEFAULT_PREFS, leadDays: 14 as const } };
    expect(derive({ contributions: { items: [far], next_due: far }, state, claims: [] }).map((n) => n.kind)).toContain("contribution-due");
  });

  it("échéance dépassée : « en retard », ton critique, même si le statut n'a pas encore basculé", () => {
    const late: MyContribution = { ...october, due_on: "2026-09-25", status: "en_retard" };
    expect(derive({ contributions: { items: [late], next_due: late } }).find((n) => n.kind === "contribution-late")).toMatchObject({ tone: "crit" });
    const notYet: MyContribution = { ...october, due_on: "2026-09-30", status: "a_payer" };
    expect(derive({ contributions: { items: [notYet], next_due: notYet } }).map((n) => n.kind)).toContain("contribution-late");
  });

  it("rien à payer : aucune notification de cotisation", () => {
    expect(derive({ contributions: { items: contributions.items.slice(1), next_due: null } }).filter((n) => n.kind.startsWith("contribution"))).toEqual([]);
  });
});

describe("remboursement passé à l'étape suivante (comparé à la dernière lecture)", () => {
  it("première lecture : aucune notification de dossier (référence posée par acknowledge)", () => {
    const state: NotificationState = { prefs: DEFAULT_PREFS, baseline: null, read: [] };
    expect(derive({ state }).filter((n) => n.kind.startsWith("claim"))).toEqual([]);
  });

  it("statut changé depuis la dernière lecture : notification avec le nouvel état, ton du statut", () => {
    const before = baseline([{ ...claimPharmacy, status: "en_revue" }, claimClinic, claimRefused]);
    const list = derive({ state: before });
    expect(list.filter((n) => n.kind === "claim-progress")).toEqual([
      expect.objectContaining({ key: `claim:${claimPharmacy.id}:accordee_auto`, tone: "ok", href: `/soins/${claimPharmacy.id}` }),
    ]);
  });

  it("nouveau dossier depuis la dernière lecture : « demande reçue »", () => {
    const list = derive({ state: baseline([claimClinic, claimRefused]) });
    expect(list.filter((n) => n.kind === "claim-new").map((n) => n.key)).toEqual([`claim:${claimPharmacy.id}:accordee_auto`]);
  });

  it("aucune donnée médicale ni montant dans les paramètres : numéro, prénom, établissement, statut", () => {
    const list = derive({ state: baseline([{ ...claimRefused, status: "en_revue" }]) });
    for (const n of list) expect(JSON.stringify(n.params)).not.toMatch(/xof|score|motif|diagnos|R-0|rule/i);
  });
});

describe("carte bloquée, couverture terminée ou qui se termine", () => {
  const kouassi = beneficiaries.items[1]!;
  it("carte bloquée d'un bénéficiaire : ton critique, lien vers sa carte", () => {
    const blocked: MyBeneficiary = { ...kouassi, card_status: "bloquee" };
    expect(derive({ beneficiaries: [beneficiaries.items[0]!, blocked] }).find((n) => n.kind === "card-blocked")).toMatchObject({
      tone: "crit",
      href: `/carte/${kouassi.person_id}`,
      params: { name: "Kouassi" },
    });
  });

  it("couverture terminée (valid_to passé) : carte expirée ; se termine dans le délai : attention", () => {
    const ended: MyBeneficiary = { ...kouassi, valid_to: "2026-09-30" };
    const ending: MyBeneficiary = { ...kouassi, person_id: "5d000000-0000-4000-8000-000000000001", valid_to: "2026-10-06" };
    const list = derive({ beneficiaries: [ended, ending] });
    expect(list.find((n) => n.kind === "card-expired")).toMatchObject({ tone: "crit", params: { name: "Kouassi", date: "30/09/2026" } });
    expect(list.find((n) => n.kind === "card-expiring")).toMatchObject({ tone: "warn", params: { date: "06/10/2026" } });
  });

  it("le titulaire mène à « / » (sa carte), un ayant droit à /carte/{id}", () => {
    const holder: MyBeneficiary = { ...beneficiaries.items[0]!, card_status: "bloquee" };
    expect(derive({ beneficiaries: [holder] }).find((n) => n.kind === "card-blocked")?.href).toBe("/");
  });
});

describe("préférences locales et lecture", () => {
  it("catégorie désactivée : ses notifications ne sont pas dérivées", () => {
    const state: NotificationState = { ...baseline([]), prefs: { ...DEFAULT_PREFS, contributions: false, claims: false } };
    const list = derive({ state, claims: [claimPharmacy] });
    expect(list.some((n) => n.kind.startsWith("contribution") || n.kind.startsWith("claim"))).toBe(false);
  });

  it("acknowledge : tout est lu, la référence des dossiers avance (les étapes lues disparaissent)", () => {
    const before = baseline([{ ...claimPharmacy, status: "en_revue" }]);
    const list = derive({ state: before, claims: [claimPharmacy] });
    expect(unreadCount(list)).toBe(2);
    const after = acknowledge(before, list, [claimPharmacy]);
    const again = derive({ state: after, claims: [claimPharmacy] });
    expect(again.filter((n) => n.kind.startsWith("claim"))).toEqual([]);
    expect(unreadCount(again)).toBe(0);
    // L'échéance reste listée (la condition tient toujours), mais comme lue.
    expect(again.find((n) => n.kind === "contribution-due")?.unread).toBe(false);
  });

  it("ordre : critique, attention, puis le reste", () => {
    const late: MyContribution = { ...october, due_on: "2026-09-25", status: "en_retard" };
    const tones = derive({ contributions: { items: [late], next_due: late }, state: baseline([{ ...claimPharmacy, status: "en_revue" }]), claims: [claimPharmacy] }).map((n) => n.tone);
    expect(tones).toEqual([...tones].sort((a, b) => ["crit", "warn", "info", "ok", "neutral"].indexOf(a) - ["crit", "warn", "info", "ok", "neutral"].indexOf(b)));
  });
});

describe("stockage local : le nécessaire seulement (empreintes et bornes)", () => {
  const ALL_IDS = [claimPharmacy, claimClinic, claimRefused].map((c) => c.id);
  const STATUSES = /accordee|payee|refusee|en_revue|a_payer|en_retard|bloquee|expiree/;

  it("sous le préfixe de l'espace ; ni identifiant de dossier, de cotisation ou de personne, ni statut, ni nom, ni montant", () => {
    expect(NOTIFICATIONS_KEY.startsWith(STORAGE_PREFIX)).toBe(true);
    const store = memoryStore();
    const list = derive({ state: baseline([{ ...claimPharmacy, status: "en_revue" }]) });
    writeNotificationState(store, acknowledge(baseline([]), list, [claimPharmacy, claimClinic]));
    const raw = store.data.get(NOTIFICATIONS_KEY) ?? "";
    expect(raw).not.toMatch(/Awa|Kouassi|Pharmacie|MC-|PEC-|27\s?500|FCFA/);
    for (const id of [...ALL_IDS, october.id, ...beneficiaries.items.map((b) => b.person_id)]) expect(raw).not.toContain(id);
    expect(raw).not.toMatch(STATUSES);
    expect(raw).not.toMatch(/claim:|contribution:|card:/);
  });

  it("relu depuis le téléphone, l'état haché suffit : rien de nouveau après lecture, une étape franchie est signalée", () => {
    const store = memoryStore();
    writeNotificationState(store, acknowledge(baseline([]), derive(), [claimPharmacy, claimClinic, claimRefused]));
    const state = readNotificationState(store);
    expect(derive({ state }).filter((n) => n.kind.startsWith("claim"))).toEqual([]);
    expect(unreadCount(derive({ state }))).toBe(0);
    const moved = derive({ state, claims: [{ ...claimPharmacy, status: "payee" }, claimClinic, claimRefused] });
    expect(moved.filter((n) => n.kind.startsWith("claim")).map((n) => n.kind)).toEqual(["claim-progress"]);
    expect(moved.find((n) => n.kind === "claim-progress")?.unread).toBe(true);
  });

  it("une notification lue (markRead) reste lue après relecture, sans garder sa clé en clair", () => {
    const store = memoryStore();
    const list = derive();
    const due = list.find((n) => n.kind === "contribution-due")!;
    writeNotificationState(store, markRead(baseline([claimPharmacy, claimClinic, claimRefused]), due.key));
    expect(store.data.get(NOTIFICATIONS_KEY)).not.toContain(october.id);
    expect(derive({ state: readNotificationState(store) }).find((n) => n.kind === "contribution-due")?.unread).toBe(false);
  });

  it("ancien état en clair (v1) : préférences gardées, identifiants et statuts effacés du téléphone", () => {
    const legacy = JSON.stringify({ v: 1, prefs: { ...DEFAULT_PREFS, leadDays: 14 }, baseline: { [claimPharmacy.id]: "payee" }, read: [`claim:${claimPharmacy.id}:payee`] });
    const store = memoryStore({ [NOTIFICATIONS_KEY]: legacy });
    expect(readNotificationState(store)).toEqual({ prefs: { ...DEFAULT_PREFS, leadDays: 14 }, baseline: null, read: [] });
    migrateNotificationState(store);
    const raw = store.data.get(NOTIFICATIONS_KEY) ?? "";
    expect(raw).not.toContain(claimPharmacy.id);
    expect(raw).not.toMatch(STATUSES);
    expect(readNotificationState(store).prefs.leadDays).toBe(14);
  });

  it("valeur illisible : préférences par défaut, aucune référence", () => {
    expect(readNotificationState(memoryStore({ [NOTIFICATIONS_KEY]: "{x" }))).toEqual({ prefs: DEFAULT_PREFS, baseline: null, read: [] });
  });

  it("la référence et les lectures sont bornées (pas d'accumulation sans fin)", () => {
    const many = Array.from({ length: 80 }, (_, i) => ({ ...claimPharmacy, id: `00000000-0000-4000-8000-${String(i).padStart(12, "0")}` }));
    const state = acknowledge(baseline([]), derive({ claims: many }), many);
    expect(state.baseline?.known.length).toBeLessThanOrEqual(50);
    expect(state.baseline?.states.length).toBeLessThanOrEqual(50);
    expect(state.read.length).toBeLessThanOrEqual(50);
  });
});
