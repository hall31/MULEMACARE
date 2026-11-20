import { tokenProvider, type TokenProvider } from "@/lib/auth";
import type {
  ClaimCreated,
  CodeSent,
  CodeVerificationRequest,
  CounterDevice,
  CreateClaimRequest,
  CurrentUser,
  Identification,
  OfflinePolicy,
  OfflineSyncRequest,
  OfflineSyncResult,
  PhotoConfirmationRequest,
  Problem,
  RegisterCounterDeviceRequest,
  StartIdentificationRequest,
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

/** Aucune réponse : réseau coupé ou injoignable. Seul cas qui autorise un accord provisoire. */
export class NetworkUnavailable extends Error {
  constructor() {
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

export interface ApiClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
  tokens?: TokenProvider;
  fetchImpl?: typeof fetch;
  isOnline?: () => boolean;
}

const DEFAULT_TIMEOUT_MS = 12_000;

function isProblem(value: unknown): value is Problem {
  return typeof value === "object" && value !== null && "code" in value && "message" in value;
}

export function createApiClient(options: ApiClientOptions = {}) {
  const baseUrl = options.baseUrl ?? "/api";
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const tokens = options.tokens ?? tokenProvider;
  const doFetch = options.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));
  const isOnline = options.isOnline ?? (() => typeof navigator === "undefined" || navigator.onLine);

  async function request<T>(method: "GET" | "POST", path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
    if (!isOnline()) throw new NetworkUnavailable();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const token = tokens.getToken();
    let response: Response;
    try {
      response = await doFetch(`${baseUrl}${path}`, {
        method,
        signal: controller.signal,
        cache: "no-store",
        headers: {
          Accept: "application/json, application/problem+json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...headers,
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch {
      if (controller.signal.aborted) throw new NetworkTimeout();
      throw new NetworkUnavailable();
    } finally {
      clearTimeout(timer);
    }
    const text = await response.text();
    const payload: unknown = text ? JSON.parse(text) : null;
    if (!response.ok) {
      if (isProblem(payload)) throw new ApiProblem(response.status, payload);
      throw new ApiProblem(response.status, {
        code: "SYS-01",
        message: "",
        action: "",
        request_id: "",
      });
    }
    return payload as T;
  }

  return {
    getCurrentUser: () => request<CurrentUser>("GET", "/v1/me"),
    getOfflinePolicy: () => request<OfflinePolicy>("GET", "/v1/counter/offline-policy"),
    registerDevice: (body: RegisterCounterDeviceRequest) => request<CounterDevice>("POST", "/v1/counter/devices", body),
    startIdentification: (body: StartIdentificationRequest) =>
      request<Identification>("POST", "/v1/counter/identifications", body),
    confirmPhoto: (id: string, body: PhotoConfirmationRequest) =>
      request<Identification>("POST", `/v1/counter/identifications/${encodeURIComponent(id)}/photo-confirmation`, body),
    sendCode: (id: string) => request<CodeSent>("POST", `/v1/counter/identifications/${encodeURIComponent(id)}/code`),
    verifyCode: (id: string, body: CodeVerificationRequest) =>
      request<Identification>("POST", `/v1/counter/identifications/${encodeURIComponent(id)}/code-verification`, body),
    createClaim: (body: CreateClaimRequest, idempotencyKey: string) =>
      request<ClaimCreated>("POST", "/v1/claims", body, { "Idempotency-Key": idempotencyKey }),
    syncOffline: (body: OfflineSyncRequest) => request<OfflineSyncResult>("POST", "/v1/authorizations/offline-sync", body),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
