import { t } from "@/i18n";
import { API_BASE_URL } from "@/lib/config";
import type { Problem } from "./types";

/**
 * Erreur métier renvoyée par l'API (application/problem+json). `message` et `action`
 * sont déjà en français simple et se montrent tels quels (AGENTS.md, Conventions).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem;

  constructor(status: number, problem: Problem) {
    super(problem.message);
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }
}

function isProblem(value: unknown): value is Problem {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as Problem).code === "string" &&
    typeof (value as Problem).message === "string"
  );
}

function fallbackProblem(kind: "network" | "unknown"): Problem {
  return {
    code: "SYS-01",
    message: kind === "network" ? t("states.networkError") : t("states.unknownError"),
    action: kind === "network" ? t("states.networkAction") : t("states.unknownAction"),
    request_id: "",
  };
}

export type Query = Record<string, string | number | boolean | undefined | null>;

export interface RequestOptions {
  token: string | null;
  method?: "GET" | "POST" | "PUT";
  query?: Query;
  body?: unknown;
  idempotencyKey?: string;
  /** Annulation (recherche remplacée par une frappe plus récente). */
  signal?: AbortSignal;
}

export async function apiRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const url = new URL(`${API_BASE_URL}${path}`);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  const headers: Record<string, string> = { Accept: "application/json, application/problem+json" };
  if (options.token) headers["Authorization"] = `Bearer ${options.token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
      signal: options.signal,
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(0, fallbackProblem("network"));
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, isProblem(payload) ? payload : fallbackProblem("unknown"));
  }
  return payload as T;
}

/** Clé d'idempotence d'une commande (8 à 200 caractères, contrat IdempotencyKey). */
export function newIdempotencyKey(): string {
  return `console-${crypto.randomUUID()}`;
}
