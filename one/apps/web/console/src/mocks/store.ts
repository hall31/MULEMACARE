/**
 * État en mémoire du serveur de mocks. Il simule les effets que les lots L1, L3 et L5
 * produiront côté API (décision humaine, écriture au grand livre, audit), pour que la
 * console soit testée sur des parcours complets. Réinitialisé à chaque chargement de page.
 */
import type { AiAction, AuditEvent, BrandingSettings, ClaimDetail, ConfigurationTemplate, LedgerEntry } from "@/api/types";
import type { ProductEventRequest } from "@/lib/telemetry";
import { DEMO_CLAIM_DETAILS, DEMO_LEDGER } from "./fixtures";
import { DEMO_TEMPLATES, INITIAL_BRANDING, TAKEN_SLUGS } from "./platform";

interface IdempotentReply {
  fingerprint: string;
  status: number;
  body: ClaimDetail;
}

interface DemoState {
  claims: ClaimDetail[];
  ledger: LedgerEntry[];
  audit: AuditEvent[];
  /** Journal de JOE (ai_actions) : chaque réponse ou brouillon avec ses sources. */
  aiActions: AiAction[];
  /** Événements de mesure produit reçus (recordProductEvent). */
  productEvents: ProductEventRequest[];
  idempotency: Map<string, IdempotentReply>;
  sequence: number;
  /** P3 : réglages de marque de l'organisation, gabarits et identifiants publics pris. */
  branding: BrandingSettings;
  templates: ConfigurationTemplate[];
  takenSlugs: string[];
}

const clone = <T>(value: T): T => structuredClone(value);

function initialState(): DemoState {
  return {
    claims: clone(DEMO_CLAIM_DETAILS),
    ledger: clone(DEMO_LEDGER),
    audit: [],
    aiActions: [],
    productEvents: [],
    idempotency: new Map(),
    sequence: 0,
    branding: clone(INITIAL_BRANDING),
    templates: clone(DEMO_TEMPLATES),
    takenSlugs: [...TAKEN_SLUGS],
  };
}

let state: DemoState = initialState();

export function resetDemoStore(): void {
  state = initialState();
}

export function demoState(): DemoState {
  return state;
}

export function auditEvents(): readonly AuditEvent[] {
  return state.audit;
}

/** Identifiant unique au format UUID v4 (compteur local, déterministe dans un test). */
export function nextId(): string {
  state.sequence += 1;
  return `00000000-0000-4000-9000-${state.sequence.toString(16).padStart(12, "0")}`;
}

export function nextEntryNumber(): string {
  const max = Math.max(...state.ledger.map((e) => Number(e.entry_number.slice(7))));
  return `J-2026-${String(max + 1).padStart(7, "0")}`;
}
