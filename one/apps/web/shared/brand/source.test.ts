import { describe, expect, it, vi } from "vitest";
import { BRANDING_FIXTURES } from "./fixtures";
import { brandQuery, domainFromHost, fetchBranding, fixtureBranding } from "./source";

describe("organisation demandée", () => {
  it("cookie de démonstration seulement en mode démonstration, puis slug du déploiement, puis domaine", () => {
    expect(brandQuery({ fixtures: true, cookieSlug: "lagune-sante", envSlug: "autre", host: "sante.lagune.ci" })).toEqual({ slug: "lagune-sante" });
    expect(brandQuery({ fixtures: false, cookieSlug: "lagune-sante", envSlug: "autre", host: "sante.lagune.ci" })).toEqual({ slug: "autre" });
    expect(brandQuery({ fixtures: false, cookieSlug: "lagune-sante", host: "sante.lagune.ci:443" })).toEqual({ domain: "sante.lagune.ci" });
    expect(brandQuery({ fixtures: true, cookieSlug: "Pas un slug", host: "127.0.0.1:3100" })).toBeNull();
  });

  it.each([["localhost:3416"], ["127.0.0.1"], ["[::1]:3000"], ["intranet"], ["app.localhost"], [""], [null], ["a b.ci"]])("pas de domaine personnalisé pour %j", (host) => {
    expect(domainFromHost(host)).toBeNull();
  });

  it("organisations fictives servies sans réseau", () => {
    expect(fixtureBranding({ slug: "lagune-sante" })).toEqual({ status: "ok", payload: BRANDING_FIXTURES["lagune-sante"] });
    expect(fixtureBranding({ slug: "inconnue" })).toEqual({ status: "absent" });
    expect(fixtureBranding({ domain: "sante.lagune.invalid" })).toEqual({ status: "absent" });
    expect(fixtureBranding(null)).toEqual({ status: "absent" });
  });
});

describe("lecture de getOrganizationBranding (sans jeton, délai borné)", () => {
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

  it("appelle /v1/public/branding avec exactement un critère, sans en-tête d'autorisation", async () => {
    const fetchImpl = vi.fn(async (_url: URL | RequestInfo, _init?: RequestInit) => json(BRANDING_FIXTURES["teranga-assurances"]));
    const load = await fetchBranding("http://api.local:8000/", { slug: "teranga-assurances" }, { fetchImpl: fetchImpl as typeof fetch });
    expect(load).toEqual({ status: "ok", payload: BRANDING_FIXTURES["teranga-assurances"] });
    const [url, init] = fetchImpl.mock.calls[0]!;
    expect(String(url)).toBe("http://api.local:8000/v1/public/branding?slug=teranga-assurances");
    expect(new Headers(init?.headers).has("authorization")).toBe(false);
    await fetchBranding("http://api.local:8000", { domain: "sante.lagune.ci" }, { fetchImpl: fetchImpl as typeof fetch });
    expect(String(fetchImpl.mock.calls[1]![0])).toBe("http://api.local:8000/v1/public/branding?domain=sante.lagune.ci");
  });

  it("404 : pas de marque ; 5xx, coupure, JSON illisible : erreur (repli)", async () => {
    expect(await fetchBranding("http://a", { slug: "abc" }, { fetchImpl: (async () => json({ code: "NOT-01" }, 404)) as typeof fetch })).toEqual({ status: "absent" });
    expect(await fetchBranding("http://a", { slug: "abc" }, { fetchImpl: (async () => json({}, 503)) as typeof fetch })).toEqual({ status: "erreur", detail: "HTTP 503" });
    expect((await fetchBranding("http://a", { slug: "abc" }, { fetchImpl: (async () => { throw new TypeError("fetch failed"); }) as typeof fetch })).status).toBe("erreur");
    expect((await fetchBranding("http://a", { slug: "abc" }, { fetchImpl: (async () => new Response("<html>", { status: 200 })) as typeof fetch })).status).toBe("erreur");
  });

  it("délai dépassé : repli sans attendre la réponse", async () => {
    const hanging = ((_url: URL, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(init.signal?.reason)))) as unknown as typeof fetch;
    const started = Date.now();
    const load = await fetchBranding("http://a", { slug: "abc" }, { fetchImpl: hanging, timeoutMs: 50 });
    expect(load).toEqual({ status: "erreur", detail: "TimeoutError" });
    expect(Date.now() - started).toBeLessThan(1_000);
  });

  it("aucune organisation demandée : aucun appel", async () => {
    const fetchImpl = vi.fn();
    expect(await fetchBranding("http://a", null, { fetchImpl: fetchImpl as unknown as typeof fetch })).toEqual({ status: "absent" });
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
