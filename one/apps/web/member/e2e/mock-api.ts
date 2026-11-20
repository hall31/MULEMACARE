import type { Page, Route } from "@playwright/test";
import { contractProblems } from "../src/test/contract-event";
import type { Checkout, MyBeneficiaryList, MyCard, MyClaimList, MyContributions, PaymentLink, Problem } from "../src/api/types";
import { TOUR_KEY } from "../src/onboarding/tour";
import {
  EXPIRED_TOKEN,
  PAYMENT_TOKEN,
  beneficiaries,
  card,
  cardKouassi,
  claims,
  contributions,
  me,
  publicLink,
  trackings,
} from "../src/test/fixtures";

/**
 * Mock de l'API pour les parcours Playwright, typé par le contrat (src/api/schema.d.ts généré
 * depuis specs/openapi.yaml) et nourri par les fixtures vérifiées par `src/contract.test.ts` :
 * une réponse hors contrat ne compile pas. Il est à état (QR qui tourne, clés d'idempotence,
 * paiement), ce que le mode statique de Prism ne permet pas. Données fictives.
 */
export const MEMBER_TOKEN = "Bearer jeton-de-test-adherent";

export interface Recorded {
  method: string;
  path: string;
  search: string;
  headers: Record<string, string>;
  body: unknown;
}

export interface Failure {
  status: number;
  problem: Omit<Problem, "request_id">;
}

function problem(p: Omit<Problem, "request_id">): Problem {
  return { ...p, request_id: "req_test" };
}

const NOT_FOUND: Failure = { status: 404, problem: { code: "NOT-01", message: "Introuvable.", action: "Vérifiez l'adresse ou revenez à l'accueil." } };

export class MockApi {
  readonly requests: Recorded[] = [];
  /** Réseau coupé : toute requête échoue sans réponse (E-NET-02 côté application). */
  networkDown = false;
  /** Durée annoncée d'une fenêtre de QR (30 s en production, Q-P1-04). */
  qrWindowMs = 30_000;
  /** Délai de réponse par chemin (états de chargement). */
  readonly delays = new Map<string, number>();
  /** Échec forcé par chemin (`/v1/me/card` → 500 SYS-01…). Une valeur `once` ne sert qu'une fois. */
  readonly failures = new Map<string, Failure & { once?: boolean }>();
  /** Coupure réseau ciblée sur la prochaine requête d'un chemin (nouvel essai après coupure). */
  readonly abortOnce = new Set<string>();
  cardPatch: Partial<MyCard> = {};
  claimsData: MyClaimList = { items: claims, page: { next_cursor: null } };
  contributionsData: MyContributions = contributions;
  beneficiariesData: MyBeneficiaryList = beneficiaries;
  /**
   * Première visite (parcours de découverte). Par défaut, les parcours existants jouent un adhérent
   * qui a déjà vu la découverte : l'état « terminé » est posé avant le premier chargement s'il
   * n'existe pas (aucune donnée de l'adhérent dans cette clé).
   */
  firstVisit = false;
  /**
   * Mesure d'usage : les parcours qui ne la testent pas jouent un adhérent qui a déjà refusé (pas
   * de bandeau de premier usage) ; « unset » laisse le téléphone vierge. Posé seulement s'il n'existe pas.
   */
  measure: "unset" | "granted" | "refused" = "refused";
  checkoutStatus: Checkout["status"] = "confirme";
  private qrCounter = 0;

  async install(page: Page): Promise<void> {
    if (!this.firstVisit) {
      await page.addInitScript((key) => {
        try {
          if (!window.localStorage.getItem(key)) window.localStorage.setItem(key, JSON.stringify({ v: 1, state: "termine", at: "2026-10-01T00:00:00.000Z" }));
        } catch {
          // Stockage indisponible (page d'erreur) : rien à poser.
        }
      }, TOUR_KEY);
    }
    if (this.measure !== "unset") {
      await page.addInitScript((choice) => {
        try {
          if (!window.localStorage.getItem("mulema.mesure.adherent")) window.localStorage.setItem("mulema.mesure.adherent", JSON.stringify({ v: 1, choice }));
        } catch {
          // Stockage indisponible (page d'erreur) : rien à poser.
        }
      }, this.measure);
    }
    await page.route("**/api/v1/**", (route) => this.handle(route));
  }

  /** Événements de mesure produit reçus (corps tels qu'envoyés). */
  events(): Record<string, unknown>[] {
    return this.requests.filter((r) => r.method === "POST" && r.path === "/v1/telemetry/events").map((r) => r.body as Record<string, unknown>);
  }

  count(path: string, method = "GET"): number {
    return this.requests.filter((r) => r.path === path && r.method === method).length;
  }

  private json(route: Route, status: number, body: unknown, problemJson = false) {
    return route.fulfill({ status, contentType: problemJson ? "application/problem+json" : "application/json", body: JSON.stringify(body) });
  }

  private fail(route: Route, failure: Failure) {
    return this.json(route, failure.status, problem(failure.problem), true);
  }

  /** QR de la fenêtre courante : charge utile fictive qui change à chaque appel. */
  private currentCard(base: MyCard): MyCard {
    this.qrCounter += 1;
    const now = Date.now();
    return {
      ...base,
      ...this.cardPatch,
      qr_payload: `MC1.carte-fictive.${base.member_number}.fenetre-${String(this.qrCounter).padStart(4, "0")}.signature-de-test`,
      qr_generated_at: new Date(now).toISOString(),
      qr_refresh_at: new Date(now + this.qrWindowMs).toISOString(),
    };
  }

  private async handle(route: Route): Promise<void> {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");
    const method = request.method();
    const body: unknown = request.postData() ? JSON.parse(request.postData() ?? "null") : null;
    this.requests.push({ method, path, search: url.search, headers: request.headers(), body });

    if (this.networkDown || this.abortOnce.delete(path)) {
      await route.abort("internetdisconnected");
      return;
    }
    const delay = this.delays.get(path);
    if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
    const failure = this.failures.get(path);
    if (failure) {
      if (failure.once) this.failures.delete(path);
      return this.fail(route, failure);
    }

    // Page publique du payeur : opérations sans jeton (security: []).
    if (path.startsWith("/v1/public/payment-links/")) return this.publicRoute(route, path, method);

    if (request.headers()["authorization"] !== MEMBER_TOKEN) {
      return this.fail(route, { status: 401, problem: { code: "AUTH-01", message: "Votre session a expiré.", action: "Reconnectez-vous puis recommencez." } });
    }
    // Mesure produit (recordProductEvent) : jugé contre le contrat comme l'API (422 sinon) ; corps relu par les tests.
    if (method === "POST" && path === "/v1/telemetry/events") {
      if (contractProblems(body).length > 0) return this.fail(route, { status: 422, problem: { code: "VAL-01", message: "Cet événement de mesure n'est pas admis.", action: "Corrigez l'événement envoyé par l'écran (liste du contrat d'API)." } });
      return route.fulfill({ status: 204 });
    }
    if (method === "GET" && path === "/v1/me") return this.json(route, 200, me);
    if (method === "GET" && path === "/v1/me/card") {
      const personId = url.searchParams.get("person_id");
      if (!personId || personId === card.person_id) return this.json(route, 200, this.currentCard(card));
      if (personId === cardKouassi.person_id) return this.json(route, 200, this.currentCard(cardKouassi));
      return this.fail(route, NOT_FOUND);
    }
    if (method === "GET" && path === "/v1/me/beneficiaries") return this.json(route, 200, this.beneficiariesData);
    if (method === "GET" && path === "/v1/me/claims") return this.json(route, 200, this.claimsData);
    const tracking = /^\/v1\/me\/claims\/([^/]+)\/tracking$/.exec(path);
    if (method === "GET" && tracking) {
      const found = trackings[decodeURIComponent(tracking[1] ?? "")];
      return found ? this.json(route, 200, found) : this.fail(route, NOT_FOUND);
    }
    if (method === "GET" && path === "/v1/me/contributions") return this.json(route, 200, this.contributionsData);
    const link = /^\/v1\/me\/contributions\/([^/]+)\/payment-links$/.exec(path);
    if (method === "POST" && link) {
      const id = decodeURIComponent(link[1] ?? "");
      const target = this.contributionsData.items.find((c) => c.id === id);
      if (!target) return this.fail(route, NOT_FOUND);
      if (target.status === "payee" || target.status === "annulee") {
        return this.fail(route, { status: 409, problem: { code: "PAY-02", message: "Cette cotisation est déjà réglée.", action: "Aucun lien n'est nécessaire." } });
      }
      const created: PaymentLink = { url: `http://127.0.0.1:3200/payer/${PAYMENT_TOKEN}`, expires_at: "2026-10-08T23:59:00Z" };
      return this.json(route, 201, created);
    }
    return this.fail(route, NOT_FOUND);
  }

  private publicRoute(route: Route, path: string, method: string) {
    const match = /^\/v1\/public\/payment-links\/([^/]+)(\/checkout)?$/.exec(path);
    const token = decodeURIComponent(match?.[1] ?? "");
    if (token === EXPIRED_TOKEN) {
      return this.fail(route, { status: 410, problem: { code: "PAY-03", message: "Ce lien de paiement a expiré.", action: "Demandez un nouveau lien à l'adhérent ou à la mutuelle." } });
    }
    if (token !== PAYMENT_TOKEN) return this.fail(route, NOT_FOUND);
    if (method === "GET" && !match?.[2]) return this.json(route, 200, publicLink);
    if (method === "POST" && match?.[2]) {
      const result: Checkout = {
        payment_id: "9f8e7d6c-5b4a-4392-8170-6f5e4d3c2b1a",
        status: this.checkoutStatus,
        redirect_url: null,
      };
      return this.json(route, 201, result);
    }
    return this.fail(route, NOT_FOUND);
  }
}
