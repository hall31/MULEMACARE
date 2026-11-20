import { browserStore, clearLastCard } from "@/card/last-card";
import { tokenProvider, type TokenProvider } from "@/lib/auth";
import type {
  Checkout,
  CheckoutRequest,
  ClaimTracking,
  CurrentUser,
  MyBeneficiaryList,
  MyCard,
  MyClaimList,
  MyContributions,
  PaymentLink,
  Problem,
  PublicPaymentLink,
} from "./types";

/** Erreur métier renvoyée par l'API (application/problem+json). */
export class ApiProblem extends Error {
  constructor(
    readonly status: number,
    readonly problem: Problem,
  ) {
    super(problem.message);
    this.name = "ApiProblem";
  }
}

/** Aucune réponse. `offline` : le téléphone se sait hors ligne (aucune requête n'est partie). */
export class NetworkUnavailable extends Error {
  constructor(readonly offline = false) {
    super("network-unavailable");
    this.name = "NetworkUnavailable";
  }
}

/** Pas de réponse dans le délai : la requête a peut-être été traitée, on rejoue la même clé. */
export class NetworkTimeout extends Error {
  constructor() {
    super("network-timeout");
    this.name = "NetworkTimeout";
  }
}

/**
 * Refus d'accès : session expirée (AUTH-01), rôle insuffisant (AUTH-02), introuvable ou hors de
 * mon contrat (NOT-01, carte révoquée), et tout 401/403/404. La carte enregistrée n'est alors
 * plus montrée et elle est effacée du téléphone.
 */
const DENIED_STATUSES: ReadonlySet<number> = new Set([401, 403, 404]);
const DENIED_CODES: ReadonlySet<string> = new Set(["AUTH-01", "AUTH-02", "NOT-01"]);

export function isAccessDenied(error: unknown): error is ApiProblem {
  return error instanceof ApiProblem && (DENIED_STATUSES.has(error.status) || DENIED_CODES.has(error.problem.code));
}

export interface ApiClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
  tokens?: TokenProvider;
  fetchImpl?: typeof fetch;
  isOnline?: () => boolean;
  /** Appelé sur un refus d'accès d'une opération `/v1/me/*`, avant que l'erreur ne remonte. */
  onAccessDenied?: (error: ApiProblem) => void;
}

const DEFAULT_TIMEOUT_MS = 12_000;

function isProblem(value: unknown): value is Problem {
  return typeof value === "object" && value !== null && "code" in value && "message" in value;
}

function parse(text: string): unknown {
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

interface RequestOptions {
  body?: unknown;
  headers?: Record<string, string>;
  /** Opération publique (`security: []`) : aucun jeton, même si un fournisseur existe. */
  anonymous?: boolean;
}

export function createApiClient(options: ApiClientOptions = {}) {
  const baseUrl = options.baseUrl ?? "/api";
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const tokens = options.tokens ?? tokenProvider;
  const doFetch = options.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const isOnline = options.isOnline ?? (() => typeof navigator === "undefined" || navigator.onLine);

  async function request<T>(method: "GET" | "POST", path: string, opts: RequestOptions = {}): Promise<T> {
    if (!isOnline()) throw new NetworkUnavailable(true);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const token = opts.anonymous ? null : tokens.getToken();
    let response: Response;
    try {
      response = await doFetch(`${baseUrl}${path}`, {
        method,
        signal: controller.signal,
        cache: "no-store",
        credentials: "same-origin",
        headers: {
          Accept: "application/json, application/problem+json",
          ...(opts.body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...opts.headers,
        },
        ...(opts.body === undefined ? {} : { body: JSON.stringify(opts.body) }),
      });
    } catch {
      if (controller.signal.aborted) throw new NetworkTimeout();
      throw new NetworkUnavailable(false);
    } finally {
      clearTimeout(timer);
    }
    const payload = parse(await response.text());
    if (!response.ok) {
      const error = isProblem(payload) ? new ApiProblem(response.status, payload) : new ApiProblem(response.status, { code: "SYS-01", message: "", action: "", request_id: "" });
      if (path.startsWith("/v1/me") && isAccessDenied(error)) options.onAccessDenied?.(error);
      throw error;
    }
    return payload as T;
  }

  const id = encodeURIComponent;

  return {
    getCurrentUser: () => request<CurrentUser>("GET", "/v1/me"),
    getMyCard: (personId?: string) => request<MyCard>("GET", personId ? `/v1/me/card?person_id=${id(personId)}` : "/v1/me/card"),
    listMyBeneficiaries: () => request<MyBeneficiaryList>("GET", "/v1/me/beneficiaries"),
    listMyClaims: (cursor?: string | null) => request<MyClaimList>("GET", cursor ? `/v1/me/claims?cursor=${id(cursor)}` : "/v1/me/claims"),
    getMyClaimTracking: (claimId: string) => request<ClaimTracking>("GET", `/v1/me/claims/${id(claimId)}/tracking`),
    listMyContributions: () => request<MyContributions>("GET", "/v1/me/contributions"),
    createMyPaymentLink: (contributionId: string, idempotencyKey: string) =>
      request<PaymentLink>("POST", `/v1/me/contributions/${id(contributionId)}/payment-links`, { headers: { "Idempotency-Key": idempotencyKey } }),
    getPublicPaymentLink: (token: string) => request<PublicPaymentLink>("GET", `/v1/public/payment-links/${id(token)}`, { anonymous: true }),
    startCheckout: (token: string, body: CheckoutRequest, idempotencyKey: string) =>
      request<Checkout>("POST", `/v1/public/payment-links/${id(token)}/checkout`, { body, anonymous: true, headers: { "Idempotency-Key": idempotencyKey } }),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

/** Client de l'application (navigateur) : un refus d'accès efface la carte enregistrée. */
export const api = createApiClient({
  onAccessDenied: () => {
    const store = browserStore();
    if (store) clearLastCard(store);
  },
});
