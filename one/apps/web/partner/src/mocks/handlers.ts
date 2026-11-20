/**
 * Serveur de mocks des espaces partenaires, dérivé de specs/openapi.yaml : seules les opérations du
 * contrat sont simulées (`handledOperations`), avec leurs rôles (`x-roles`) et leurs erreurs
 * (`Problem`, codes stables) ; chaque réponse est validée par tests/unit/contract.test.ts.
 */
import { http, HttpResponse, type HttpResponseResolver } from "msw";
import type { ErrorCode, Role } from "@/api/types";
import { API_BASE_URL } from "@/lib/config";
import { roleFromDemoToken } from "@/lib/session";
import { DEMO_USERS, daysBetween, employerConsumption, employerContracts, insurerPortfolio, portfolioCsv, publishedPeriod, today } from "./data";

export interface HandledOperation {
  method: "get";
  path: string;
}
export const handledOperations: HandledOperation[] = [];

function problem(status: number, code: ErrorCode, message: string, action: string, extra: Record<string, unknown> = {}) {
  return HttpResponse.json({ code, message, action, request_id: `req_demo_${Math.random().toString(36).slice(2, 10)}`, ...extra }, { status, headers: { "Content-Type": "application/problem+json" } });
}

type Resolver = (args: { request: Request; role: Role }) => Response | Promise<Response>;

function route(path: string, roles: Role[], resolver: Resolver) {
  handledOperations.push({ method: "get", path });
  const handler: HttpResponseResolver = ({ request }) => {
    const role = roleFromDemoToken((request.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, ""));
    if (!role) return problem(401, "AUTH-01", "Votre session a expiré.", "Reconnectez-vous puis recommencez.");
    if (!roles.includes(role)) return problem(403, "AUTH-02", "Votre rôle ne permet pas cette action.", "Demandez l'accès à l'administrateur de votre organisation.");
    return resolver({ request, role });
  };
  return http.get(`${API_BASE_URL}${path}`, handler);
}

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Période `from`/`to` (jours locaux inclus, 366 au plus, 30 derniers jours par défaut). */
function period(request: Request): { from: string; to: string } | Response {
  const url = new URL(request.url);
  const to = url.searchParams.get("to") ?? today();
  const from = url.searchParams.get("from") ?? new Date(Date.parse(`${to}T00:00:00Z`) - 29 * 86_400_000).toISOString().slice(0, 10);
  if (!DATE.test(from) || !DATE.test(to) || from > to || daysBetween(from, to) > 366) {
    return problem(422, "VAL-01", "La période demandée est invalide.", "Choisissez une période de 366 jours au plus, début avant fin.", { errors: [{ field: "from", message: "Période de 1 à 366 jours." }] });
  }
  // CR-P3-02 : semaines civiles entières, coupées à la dernière semaine terminée.
  const published = publishedPeriod(from, to);
  if (!published) {
    return problem(422, "VAL-01", "Aucune semaine complète n'est encore terminée sur cette période.", "Choisissez une période qui inclut une semaine terminée, par exemple les 30 derniers jours.", { errors: [{ field: "to", message: "Aucune semaine terminée." }] });
  }
  return published;
}

export const handlers = [
  route("/v1/me", ["assureur", "employeur"], ({ role }) => HttpResponse.json(DEMO_USERS[role as keyof typeof DEMO_USERS])),
  route("/v1/insurer/portfolio", ["assureur", "admin"], ({ request }) => {
    const p = period(request);
    return p instanceof Response ? p : HttpResponse.json(insurerPortfolio(p.from, p.to));
  }),
  route("/v1/insurer/portfolio/export", ["assureur", "admin"], ({ request }) => {
    const p = period(request);
    return p instanceof Response ? p : new HttpResponse(portfolioCsv(insurerPortfolio(p.from, p.to)), { headers: { "Content-Type": "text/csv; charset=utf-8" } });
  }),
  route("/v1/employer/consumption", ["employeur"], ({ request }) => {
    const p = period(request);
    return p instanceof Response ? p : HttpResponse.json(employerConsumption(p.from, p.to));
  }),
  route("/v1/employer/contracts", ["employeur"], ({ request }) => {
    const raw = new URL(request.url).searchParams.get("within_days");
    const within = raw === null ? 90 : Number(raw);
    if (!Number.isInteger(within) || within < 1 || within > 365) {
      return problem(422, "VAL-01", "L'horizon d'échéance est invalide.", "Choisissez un horizon de 1 à 365 jours.", { errors: [{ field: "within_days", message: "1 à 365 jours." }] });
    }
    return HttpResponse.json(employerContracts(within));
  }),
];
