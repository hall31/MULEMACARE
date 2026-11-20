import type { components } from "@/api/schema";
import { measureOffForInstance, readMeasureChoice } from "./measure-consent";

/**
 * Mesure produit (CR-P2-01, opération `recordProductEvent`, x-lot P2) : petit client typé par le
 * contrat. Liste blanche FERMÉE d'événements, propriétés bornées (variante, étape, durée) : aucun
 * texte libre, aucun identifiant de personne. Identifiant de session tiré au hasard à chaque
 * chargement (16 octets de `crypto.getRandomValues`, 32 caractères hexadécimaux, CR-P2-02), gardé
 * en mémoire seulement (jamais stocké dans le navigateur).
 *
 * Envoi non bloquant (`keepalive`, jamais attendu), silencieux : hors ligne, l'événement attend en
 * mémoire (20 au plus) le retour du réseau ; une erreur n'est ni affichée ni réessayée.
 * Consentement d'abord : rien n'est envoyé tant que la personne n'a pas accepté la mesure
 * (`measure-consent.ts`) ; `NEXT_PUBLIC_MULEMA_TELEMETRY=off` la coupe pour toute l'instance.
 */
type S = components["schemas"];
export type ProductEventName = S["ProductEventName"];
export type ProductEventRequest = S["ProductEventRequest"];
export type ProductSurface = S["ProductSurface"];
export type ProductEventVariant = S["ProductEventVariant"];
type Role = S["Role"];

interface EventRule {
  surfaces: readonly ProductSurface[];
  /** Vide : aucune variante admise ; sinon une variante de la liste est exigée. */
  variants?: readonly ProductEventVariant[];
  step?: boolean;
  /** Absente : durée refusée (l'API répond 422). `exigee` : sans durée valide, rien n'est envoyé. */
  duration?: { mode: "exigee" | "admise"; maxMs: number };
}

const ALL: readonly ProductSurface[] = ["console", "comptoir", "espace_adherent"];

/** Bornes de CR-P2-02 : au-delà, ce n'est plus un affichage de décision ni un parcours d'accueil. */
export const COUNTER_MAX_DURATION_MS = 300_000;
export const ONBOARDING_MAX_DURATION_MS = 3_600_000;

/** Miroir des règles de l'API (apps/api/metrics/catalog.py) ; exhaustif par construction. */
export const EVENT_RULES: Record<ProductEventName, EventRule> = {
  onboarding_started: { surfaces: ALL },
  onboarding_step: { surfaces: ALL, step: true },
  onboarding_completed: { surfaces: ALL, duration: { mode: "admise", maxMs: ONBOARDING_MAX_DURATION_MS } },
  card_presented: { surfaces: ["espace_adherent"], variants: ["en_ligne", "hors_ligne"] },
  counter_decision_shown: { surfaces: ["comptoir"], variants: ["accordee", "revue", "refusee"], duration: { mode: "exigee", maxMs: COUNTER_MAX_DURATION_MS } },
  payment_link_created: { surfaces: ["espace_adherent", "console"] },
  palette_opened: { surfaces: ["console"], variants: ["clavier", "bouton"] },
  joe_question_asked: { surfaces: ["console"], variants: ["exemple", "saisie"] },
  notification_opened: { surfaces: ALL, variants: ["sms", "whatsapp", "in_app"] },
  offline_banner_seen: { surfaces: ["comptoir", "espace_adherent"] },
  claim_tracking_viewed: { surfaces: ["espace_adherent"] },
};

export interface EventProps {
  variant?: ProductEventVariant;
  step?: number;
  duration_ms?: number;
}

/** Corps de l'événement, ou null si les règles le refusent (il n'est alors pas envoyé). */
export function buildEvent(name: ProductEventName, props: EventProps, ctx: { surface: ProductSurface; role: Role; sessionId: string }): ProductEventRequest | null {
  const rule = EVENT_RULES[name];
  if (!rule.surfaces.includes(ctx.surface)) return null;
  const event: ProductEventRequest = { name, surface: ctx.surface, role: ctx.role, session_id: ctx.sessionId };
  if (rule.variants && rule.variants.length > 0) {
    if (!props.variant || !rule.variants.includes(props.variant)) return null;
    event.variant = props.variant;
  } else if (props.variant !== undefined) return null;
  if (rule.step) {
    if (props.step === undefined || !Number.isInteger(props.step) || props.step < 1 || props.step > 20) return null;
    event.step = props.step;
  } else if (props.step !== undefined) return null;
  if (rule.duration) {
    const ms = props.duration_ms === undefined ? Number.NaN : Math.round(props.duration_ms);
    if (Number.isFinite(ms) && ms >= 0 && ms <= rule.duration.maxMs) event.duration_ms = ms;
    // Durée exigée absente ou hors borne : rien. Admise : l'événement part, sans la durée.
    else if (rule.duration.mode === "exigee") return null;
  } else if (props.duration_ms !== undefined) return null;
  return event;
}

/**
 * 16 octets de `crypto.getRandomValues` en hexadécimal minuscule : exactement `^[0-9a-f]{32}$`
 * (contrat, CR-P2-02). Jamais fait que de chiffres (l'API le refuse) : le premier caractère devient
 * alors une lettre, cas d'une chance sur trois millions environ.
 */
export function newSessionId(random: (bytes: Uint8Array) => Uint8Array = (b) => crypto.getRandomValues(b)): string {
  const id = Array.from(random(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
  return /^[0-9]+$/.test(id) ? `a${id.slice(1)}` : id;
}

export interface TelemetryOptions {
  surface: ProductSurface;
  role: Role;
  send: (event: ProductEventRequest, token: string) => Promise<void>;
  isOnline: () => boolean;
  isEnabled: () => boolean;
  getToken: () => string | null;
}

const MAX_PENDING = 20;

export class Telemetry {
  readonly sessionId = newSessionId();
  private readonly pending: ProductEventRequest[] = [];

  constructor(private readonly options: TelemetryOptions) {}

  track(name: ProductEventName, props: EventProps = {}): void {
    try {
      if (!this.options.isEnabled()) {
        this.pending.length = 0;
        return;
      }
      const event = buildEvent(name, props, { surface: this.options.surface, role: this.options.role, sessionId: this.sessionId });
      if (!event) return;
      if (!this.options.isOnline()) {
        if (this.pending.length < MAX_PENDING) this.pending.push(event);
        return;
      }
      this.dispatch(event);
    } catch {
      // La mesure ne gêne jamais l'écran.
    }
  }

  /** Retour du réseau : envoie ce qui attendait (une seule fois). */
  flush(): void {
    if (!this.options.isEnabled()) {
      // Refus pendant une coupure : ce qui attendait est oublié, jamais envoyé plus tard.
      this.pending.length = 0;
      return;
    }
    if (!this.options.isOnline()) return;
    for (const event of this.pending.splice(0)) this.dispatch(event);
  }

  private dispatch(event: ProductEventRequest): void {
    const token = this.options.getToken();
    if (!token) return;
    this.options.send(event, token).catch(() => undefined);
  }
}

/* ------------------------------------------------------------------ console */

/** Ancienne clé de l'interrupteur (« off »), relue comme un refus par `measure-consent.ts`. */
export const TELEMETRY_KEY = "mulemacare-one.console.mesure";

/** Vrai seulement si la personne a accepté la mesure et que l'instance ne l'a pas coupée. */
export function telemetryEnabled(): boolean {
  if (measureOffForInstance()) return false;
  return readMeasureChoice() === "granted";
}

/** Envoi vers l'API de l'instance (jamais ailleurs), sans attendre la réponse. */
export function sendToApi(baseUrl: string) {
  return async (event: ProductEventRequest, token: string): Promise<void> => {
    await fetch(`${baseUrl}/v1/telemetry/events`, {
      method: "POST",
      keepalive: true,
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(event),
    });
  };
}
