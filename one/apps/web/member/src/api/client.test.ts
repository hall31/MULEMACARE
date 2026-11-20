import { describe, expect, it } from "vitest";
import { ApiProblem, NetworkTimeout, NetworkUnavailable, createApiClient } from "./client";
import { isAccessDenied, toUiError } from "./errors";
import { card, publicLink } from "@/test/fixtures";

interface Call {
  url: string;
  init: RequestInit;
}

function fakeFetch(status: number, body: unknown, calls: Call[], contentType = "application/json"): typeof fetch {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init: init ?? {} });
    return new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": contentType } });
  }) as typeof fetch;
}

const tokens = { getToken: () => "jeton-x" };

function header(call: Call | undefined, name: string): string | undefined {
  return (call?.init.headers as Record<string, string> | undefined)?.[name];
}

describe("client de l'espace adhérent (contrat P1)", () => {
  it("appelle les opérations P1 avec le jeton, sans jamais passer le contrat dans la requête", async () => {
    const calls: Call[] = [];
    const api = createApiClient({ fetchImpl: fakeFetch(200, card, calls), tokens, isOnline: () => true });
    await api.getMyCard();
    await api.getMyCard("5b1c0d2e-3f40-4a51-8b62-7c83d94ea5f6");
    await api.listMyBeneficiaries();
    await api.listMyClaims();
    await api.listMyClaims("c-2");
    await api.getMyClaimTracking("e1d2c3b4-a596-4877-8695-a4b3c2d1e0f1");
    await api.listMyContributions();
    expect(calls.map((c) => c.url)).toEqual([
      "/api/v1/me/card",
      "/api/v1/me/card?person_id=5b1c0d2e-3f40-4a51-8b62-7c83d94ea5f6",
      "/api/v1/me/beneficiaries",
      "/api/v1/me/claims",
      "/api/v1/me/claims?cursor=c-2",
      "/api/v1/me/claims/e1d2c3b4-a596-4877-8695-a4b3c2d1e0f1/tracking",
      "/api/v1/me/contributions",
    ]);
    for (const call of calls) {
      expect(header(call, "Authorization")).toBe("Bearer jeton-x");
      expect(call.init.cache).toBe("no-store");
    }
  });

  it("crée un lien de paiement avec la clé d'idempotence fournie (rejouée telle quelle)", async () => {
    const calls: Call[] = [];
    const api = createApiClient({ fetchImpl: fakeFetch(201, { url: "https://x.invalid/payer/t", expires_at: "2026-10-08T00:00:00Z" }, calls), tokens, isOnline: () => true });
    await api.createMyPaymentLink("c0c0c0c0-0000-4000-8000-000000000001", "cle-1");
    await api.createMyPaymentLink("c0c0c0c0-0000-4000-8000-000000000001", "cle-1");
    expect(calls).toHaveLength(2);
    expect(calls[0]?.url).toBe("/api/v1/me/contributions/c0c0c0c0-0000-4000-8000-000000000001/payment-links");
    expect(calls[0]?.init.method).toBe("POST");
    expect(calls.map((c) => header(c, "Idempotency-Key"))).toEqual(["cle-1", "cle-1"]);
  });

  it("page publique du payeur : aucun jeton envoyé, même si un fournisseur d'identité existe", async () => {
    const calls: Call[] = [];
    const api = createApiClient({ fetchImpl: fakeFetch(200, publicLink, calls), tokens, isOnline: () => true });
    await api.getPublicPaymentLink("tok/en");
    await api.startCheckout("tok/en", { channel: "wave" }, "cle-2");
    expect(calls[0]?.url).toBe("/api/v1/public/payment-links/tok%2Fen");
    expect(calls[1]?.url).toBe("/api/v1/public/payment-links/tok%2Fen/checkout");
    expect(calls[1]?.init.body).toBe(JSON.stringify({ channel: "wave" }));
    for (const call of calls) expect(header(call, "Authorization")).toBeUndefined();
    expect(header(calls[1], "Idempotency-Key")).toBe("cle-2");
  });

  it("erreur métier : ApiProblem avec le code stable du contrat", async () => {
    const problem = { code: "PAY-03", message: "Ce lien de paiement a expiré.", action: "Demandez un nouveau lien.", request_id: "r1" };
    const api = createApiClient({ fetchImpl: fakeFetch(410, problem, [], "application/problem+json"), isOnline: () => true });
    const error = await api.getPublicPaymentLink("t").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiProblem);
    expect((error as ApiProblem).status).toBe(410);
    expect(toUiError(error)).toEqual({ text: problem.message, detail: problem.action, code: "PAY-03" });
  });

  it("réponse hors contrat (pas de problem+json) : SYS-01, jamais un message vide", async () => {
    const api = createApiClient({ fetchImpl: fakeFetch(502, undefined, []), isOnline: () => true });
    const ui = toUiError(await api.getMyCard().catch((e: unknown) => e));
    expect(ui.code).toBe("SYS-01");
    expect(ui.text.length).toBeGreaterThan(10);
    expect(ui.detail?.length ?? 0).toBeGreaterThan(10);
  });

  it("hors ligne, sans réponse, délai dépassé : codes E-NET-01, E-NET-02, E-NET-03", async () => {
    const offline = createApiClient({ isOnline: () => false });
    const offlineError = await offline.getMyCard().catch((e: unknown) => e);
    expect(offlineError).toBeInstanceOf(NetworkUnavailable);
    expect(toUiError(offlineError).code).toBe("E-NET-01");

    const refused = createApiClient({ isOnline: () => true, fetchImpl: (async () => Promise.reject(new TypeError("Failed to fetch"))) as typeof fetch });
    const refusedError = await refused.getMyCard().catch((e: unknown) => e);
    expect(refusedError).toBeInstanceOf(NetworkUnavailable);
    expect(toUiError(refusedError).code).toBe("E-NET-02");

    const slow = createApiClient({
      isOnline: () => true,
      timeoutMs: 5,
      fetchImpl: ((_input: RequestInfo | URL, init?: RequestInit) =>
        new Promise((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))))) as typeof fetch,
    });
    const slowError = await slow.getMyCard().catch((e: unknown) => e);
    expect(slowError).toBeInstanceOf(NetworkTimeout);
    expect(toUiError(slowError).code).toBe("E-NET-03");
  });

  it("refus d'accès sur /v1/me/* (401, 403, 404, AUTH-01, AUTH-02, NOT-01) : le client prévient pour effacer la carte enregistrée", async () => {
    const cases: [number, string, (api: ReturnType<typeof createApiClient>) => Promise<unknown>][] = [
      [401, "AUTH-01", (a) => a.getMyCard()],
      [403, "AUTH-02", (a) => a.listMyClaims()],
      [404, "NOT-01", (a) => a.getMyCard("5b1c0d2e-3f40-4a51-8b62-7c83d94ea5f6")],
      [404, "ID-06", (a) => a.getMyClaimTracking("x")],
      [403, "SEC-01", (a) => a.listMyContributions()],
      // Code de refus sous un autre statut : purgé aussi.
      [400, "AUTH-01", (a) => a.listMyBeneficiaries()],
    ];
    for (const [status, code, call] of cases) {
      const denied: string[] = [];
      const api = createApiClient({
        fetchImpl: fakeFetch(status, { code, message: "m", action: "a", request_id: "r" }, [], "application/problem+json"),
        tokens,
        isOnline: () => true,
        onAccessDenied: (error) => denied.push(error.problem.code),
      });
      const error = await call(api).catch((e: unknown) => e);
      expect(error, code).toBeInstanceOf(ApiProblem);
      expect(isAccessDenied(error), code).toBe(true);
      expect(denied, `${status} ${code}`).toEqual([code]);
    }
  });

  it("pas de purge sur une panne du serveur, une coupure réseau ou la page publique du payeur", async () => {
    const denied: string[] = [];
    const onAccessDenied = (error: ApiProblem) => denied.push(error.problem.code);
    const down = createApiClient({ fetchImpl: fakeFetch(503, { code: "SYS-01", message: "m", action: "a", request_id: "r" }, [], "application/problem+json"), isOnline: () => true, onAccessDenied });
    expect(isAccessDenied(await down.getMyCard().catch((e: unknown) => e))).toBe(false);
    const offline = createApiClient({ isOnline: () => false, onAccessDenied });
    expect(isAccessDenied(await offline.getMyCard().catch((e: unknown) => e))).toBe(false);
    const payer = createApiClient({ fetchImpl: fakeFetch(404, { code: "NOT-01", message: "m", action: "a", request_id: "r" }, [], "application/problem+json"), isOnline: () => true, onAccessDenied });
    await payer.getPublicPaymentLink("inconnu").catch(() => undefined);
    expect(denied).toEqual([]);
  });

  it("toute erreur affichée porte un code, une phrase et une action", () => {
    for (const error of [new Error("x"), "texte", null, new NetworkUnavailable(true), new NetworkTimeout()]) {
      const ui = toUiError(error);
      expect(ui.code).toMatch(/^[A-Z]+(-[A-Z]+)?-\d{2}$/);
      expect(ui.text).not.toBe("");
      expect(ui.detail).toBeTruthy();
    }
  });
});
