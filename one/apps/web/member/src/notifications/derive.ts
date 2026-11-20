import type { ClaimStatus, MyBeneficiary, MyClaim, MyContributions } from "@/api/types";
import type { KeyValueStore } from "@/card/last-card";
import { formatDateOnly, formatMonth, withDe } from "@/lib/format";
import { CLAIM_STATUS, type StatusTone } from "@/ui/tones";

/**
 * Centre de notifications de l'espace adhérent (Phase 2, voie A), DÉRIVÉ des données déjà servies
 * par le contrat (listMyContributions, listMyClaims, listMyBeneficiaries) : aucun nouvel endpoint,
 * aucun envoi (SMS et WhatsApp hors périmètre). Fonctions pures, testées sans navigateur.
 *
 * « Passé à l'étape suivante » se calcule en comparant chaque dossier à la dernière lecture
 * (`baseline`). Le téléphone ne garde que le nécessaire, en EMPREINTES : celle de chaque dossier
 * connu et celle de son état (dossier + statut), et celles des notifications lues. Aucun
 * identifiant de dossier, de cotisation ou de personne, aucun statut, aucun montant, aucun nom en
 * clair ; 50 entrées au plus. Le contrat ne date pas les changements de statut (CR-P2-03).
 */
export const NOTIFICATIONS_KEY = "mulema.adherent.notifications";

/** Au-delà, les plus anciennes entrées sont oubliées (pas d'accumulation sans fin). */
const MAX_ENTRIES = 50;

export const LEAD_DAYS = [3, 7, 14] as const;
export type LeadDays = (typeof LEAD_DAYS)[number];

export interface NotificationPrefs {
  contributions: boolean;
  claims: boolean;
  cards: boolean;
  /** Délai d'alerte avant une échéance de cotisation (choix de l'adhérent, pas une règle métier). */
  leadDays: LeadDays;
}

export const DEFAULT_PREFS: NotificationPrefs = { contributions: true, claims: true, cards: true, leadDays: 7 };

/** Empreintes des dossiers à la dernière lecture : dossier connu, et dossier dans tel statut. */
export interface ClaimBaseline {
  known: string[];
  states: string[];
}

export interface NotificationState {
  prefs: NotificationPrefs;
  /** Référence de la dernière lecture (empreintes) ; null tant qu'aucune lecture n'a eu lieu. */
  baseline: ClaimBaseline | null;
  /** Empreintes des notifications lues. */
  read: string[];
}

/**
 * Empreinte courte et non réversible d'une clé (cyrb53, 53 bits, hexadécimal) : sert seulement à
 * reconnaître une clé déjà vue sur ce téléphone, jamais à la retrouver. Synchrone (calcul pur).
 */
export function fingerprint(value: string): string {
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < value.length; i += 1) {
    const ch = value.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16).padStart(14, "0");
}

const claimKnown = (id: string) => fingerprint(`dossier:${id}`);
const claimState = (id: string, status: ClaimStatus) => fingerprint(`dossier:${id}:${status}`);
const HASH = /^[0-9a-f]{14}$/;

export type NotificationKind = "contribution-late" | "contribution-due" | "claim-progress" | "claim-new" | "card-blocked" | "card-expired" | "card-expiring";

export interface AppNotification {
  key: string;
  kind: NotificationKind;
  tone: StatusTone;
  href: string;
  params: Record<string, string | number>;
  unread: boolean;
}

export interface DeriveInput {
  /** Date du jour (AAAA-MM-JJ) dans le fuseau de l'organisation. */
  today: string;
  contributions?: MyContributions | undefined;
  claims?: readonly MyClaim[] | undefined;
  beneficiaries?: readonly MyBeneficiary[] | undefined;
  state: NotificationState;
}

const DAY_MS = 86_400_000;

/** Jours entre deux dates calendaires (AAAA-MM-JJ), sans fuseau. */
export function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / DAY_MS);
}

/** Date calendaire du jour dans un fuseau (Abidjan, Dakar). */
export function localDay(now: Date, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

const TONE_ORDER: StatusTone[] = ["crit", "warn", "info", "ok", "neutral"];

export function deriveNotifications({ today, contributions, claims = [], beneficiaries = [], state }: DeriveInput): AppNotification[] {
  const { prefs } = state;
  const read = new Set(state.read);
  const known = new Set(state.baseline?.known ?? []);
  const states = new Set(state.baseline?.states ?? []);
  const out: Omit<AppNotification, "unread">[] = [];

  const due = contributions?.next_due ?? null;
  if (prefs.contributions && due && (due.status === "a_payer" || due.status === "en_retard")) {
    const days = daysBetween(today, due.due_on);
    const params = { month: withDe(formatMonth(due.period_start)), date: formatDateOnly(due.due_on), days: Math.abs(days) };
    if (due.status === "en_retard" || days < 0) {
      out.push({ key: `contribution:${due.id}:en_retard`, kind: "contribution-late", tone: "crit", href: "/cotisations", params });
    } else if (days <= prefs.leadDays) {
      out.push({ key: `contribution:${due.id}:a_payer`, kind: "contribution-due", tone: "warn", href: "/cotisations", params });
    }
  }

  if (prefs.claims && state.baseline) {
    for (const claim of claims) {
      if (states.has(claimState(claim.id, claim.status))) continue;
      out.push({
        key: `claim:${claim.id}:${claim.status}`,
        kind: known.has(claimKnown(claim.id)) ? "claim-progress" : "claim-new",
        tone: CLAIM_STATUS[claim.status].tone,
        href: `/soins/${claim.id}`,
        params: { number: claim.claim_number, name: claim.beneficiary_given_name, provider: claim.provider_name, status: claim.status },
      });
    }
  }

  if (prefs.cards) {
    for (const b of beneficiaries) {
      const href = b.relationship === "titulaire" ? "/" : `/carte/${b.person_id}`;
      if (b.valid_to && daysBetween(today, b.valid_to) < 0) {
        out.push({ key: `card:${b.person_id}:expiree:${b.valid_to}`, kind: "card-expired", tone: "crit", href, params: { name: b.given_name, date: formatDateOnly(b.valid_to) } });
        continue;
      }
      if (b.card_status === "bloquee") {
        out.push({ key: `card:${b.person_id}:bloquee`, kind: "card-blocked", tone: "crit", href, params: { name: b.given_name } });
      }
      if (b.valid_to && daysBetween(today, b.valid_to) <= prefs.leadDays) {
        out.push({ key: `card:${b.person_id}:fin:${b.valid_to}`, kind: "card-expiring", tone: "warn", href, params: { name: b.given_name, date: formatDateOnly(b.valid_to) } });
      }
    }
  }

  return out
    .map((n, i) => ({ n, i }))
    .sort((a, b) => TONE_ORDER.indexOf(a.n.tone) - TONE_ORDER.indexOf(b.n.tone) || a.i - b.i)
    .map(({ n }) => ({ ...n, unread: !read.has(fingerprint(n.key)) }));
}

export function unreadCount(list: readonly AppNotification[]): number {
  return list.filter((n) => n.unread).length;
}

/** Référence des dossiers (les plus récents d'abord, bornée) : empreintes seulement. */
export function baselineOf(claims: readonly MyClaim[]): ClaimBaseline {
  const recent = claims.slice(0, MAX_ENTRIES);
  return { known: recent.map((c) => claimKnown(c.id)), states: recent.map((c) => claimState(c.id, c.status)) };
}

/** « Tout marquer comme lu » : lectures enregistrées, référence des dossiers avancée. */
export function acknowledge(state: NotificationState, list: readonly AppNotification[], claims: readonly MyClaim[]): NotificationState {
  const read = [...new Set([...list.map((n) => fingerprint(n.key)), ...state.read])].slice(0, MAX_ENTRIES);
  return { ...state, baseline: baselineOf(claims), read };
}

/** Une notification ouverte : marquée lue (son empreinte, jamais sa clé). */
export function markRead(state: NotificationState, key: string): NotificationState {
  const mark = fingerprint(key);
  return { ...state, read: [mark, ...state.read.filter((k) => k !== mark)].slice(0, MAX_ENTRIES) };
}

/* ------------------------------------------------------------------ stockage */

interface Stored {
  v: 2;
  prefs: NotificationPrefs;
  baseline: ClaimBaseline | null;
  read: string[];
}

const EMPTY: NotificationState = { prefs: DEFAULT_PREFS, baseline: null, read: [] };

function validPrefs(value: unknown): NotificationPrefs {
  const p = (value ?? {}) as Partial<NotificationPrefs>;
  return {
    contributions: typeof p.contributions === "boolean" ? p.contributions : DEFAULT_PREFS.contributions,
    claims: typeof p.claims === "boolean" ? p.claims : DEFAULT_PREFS.claims,
    cards: typeof p.cards === "boolean" ? p.cards : DEFAULT_PREFS.cards,
    leadDays: (LEAD_DAYS as readonly number[]).includes(p.leadDays ?? -1) ? (p.leadDays as LeadDays) : DEFAULT_PREFS.leadDays,
  };
}

/** Empreintes valides seulement (une valeur en clair glissée là n'est jamais relue). */
function hashes(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((k): k is string => typeof k === "string" && HASH.test(k)).slice(0, MAX_ENTRIES) : [];
}

function validBaseline(value: unknown): ClaimBaseline | null {
  if (!value || typeof value !== "object") return null;
  const b = value as Partial<ClaimBaseline>;
  return { known: hashes(b.known), states: hashes(b.states) };
}

/**
 * État relu du téléphone. Version 1 (statuts et identifiants en clair) : seules les préférences
 * sont reprises ; la référence repart de zéro (posée en silence à la prochaine lecture).
 */
export function readNotificationState(store: KeyValueStore): NotificationState {
  try {
    const raw = store.getItem(NOTIFICATIONS_KEY);
    if (!raw) return EMPTY;
    const value = JSON.parse(raw) as { v?: unknown; prefs?: unknown; baseline?: unknown; read?: unknown };
    if (value.v === 1) return { ...EMPTY, prefs: validPrefs(value.prefs) };
    if (value.v !== 2) return EMPTY;
    return { prefs: validPrefs(value.prefs), baseline: validBaseline(value.baseline), read: hashes(value.read) };
  } catch {
    return EMPTY;
  }
}

export function writeNotificationState(store: KeyValueStore, state: NotificationState): void {
  const stored: Stored = { v: 2, prefs: state.prefs, baseline: state.baseline ? { known: hashes(state.baseline.known), states: hashes(state.baseline.states) } : null, read: hashes(state.read) };
  try {
    store.setItem(NOTIFICATIONS_KEY, JSON.stringify(stored));
  } catch {
    // Stockage refusé : les notifications restent calculées, sans mémoire de lecture.
  }
}

/** Réécrit tout état d'une version antérieure : plus rien en clair sur le téléphone. */
export function migrateNotificationState(store: KeyValueStore): void {
  try {
    const raw = store.getItem(NOTIFICATIONS_KEY);
    if (!raw) return;
    const version = (JSON.parse(raw) as { v?: unknown }).v;
    if (version !== 2) writeNotificationState(store, readNotificationState(store));
  } catch {
    writeNotificationState(store, EMPTY);
  }
}
