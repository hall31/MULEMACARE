import { t } from "@/i18n";
import { API_BASE_URL } from "@/lib/config";
import type { Problem } from "./types";

/** Erreur métier (application/problem+json) : `message` et `action` se montrent tels quels. */
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
  return typeof value === "object" && value !== null && typeof (value as Problem).code === "string" && typeof (value as Problem).message === "string";
}

function fallbackProblem(kind: "network" | "unknown"): Problem {
  return {
    code: "SYS-01",
    message: kind === "network" ? t("states.networkError") : t("states.unknownError"),
    action: kind === "network" ? t("states.networkAction") : t("states.unknownAction"),
    request_id: "",
  };
}

export type Query = Record<string, string | number | undefined | null>;

async function send(path: string, token: string | null, query: Query, accept: string): Promise<Response> {
  const url = new URL(`${API_BASE_URL}${path}`);
  for (const [key, value] of Object.entries(query)) if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  const headers: Record<string, string> = { Accept: `${accept}, application/problem+json` };
  if (token) headers.Authorization = `Bearer ${token}`;
  let response: Response;
  try {
    response = await fetch(url, { headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, fallbackProblem("network"));
  }
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, isProblem(payload) ? payload : fallbackProblem("unknown"));
  }
  return response;
}

export async function apiGet<T>(path: string, token: string | null, query: Query = {}): Promise<T> {
  return (await (await send(path, token, query, "application/json")).json()) as T;
}

/** Export agrégé (CSV, `exportInsurerPortfolio`) : le texte reçu, tel quel. */
export async function apiGetText(path: string, token: string | null, query: Query = {}): Promise<string> {
  return (await send(path, token, query, "text/csv")).text();
}
