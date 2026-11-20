import { describe, expect, it, vi } from "vitest";
import { BRANDING_FIXTURES } from "./fixtures";
import { describeFallback, loadBrand } from "./load";

describe("marque d'une requête", () => {
  it("démonstration : organisation du cookie, sans réseau", async () => {
    const fetchImpl = vi.fn();
    const brand = await loadBrand({ fixtures: true, cookieSlug: "teranga-assurances", apiUrl: "http://a", fetchOptions: { fetchImpl: fetchImpl as unknown as typeof fetch } });
    expect(brand.identity?.displayName).toBe("Teranga Assurances");
    expect(brand.css).toContain("--accent:#0b5f8a;");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("démonstration sans cookie : thème MulemaCare", async () => {
    expect((await loadBrand({ fixtures: true, apiUrl: "http://a" })).css).toBe("");
  });

  it("production : le cookie est ignoré, l'API est lue par domaine", async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify(BRANDING_FIXTURES["lagune-sante"]), { status: 200 }));
    const brand = await loadBrand({ fixtures: false, cookieSlug: "marque-agressive", host: "sante.lagune.invalid", apiUrl: "http://api", fetchOptions: { fetchImpl: fetchImpl as unknown as typeof fetch } });
    expect(String((fetchImpl.mock.calls[0] as unknown[])[0])).toBe("http://api/v1/public/branding?domain=sante.lagune.invalid");
    expect(brand.identity?.slug).toBe("lagune-sante");
  });

  it("marque agressive : repli signalé en clair (console de développement)", async () => {
    const brand = await loadBrand({ fixtures: true, cookieSlug: "marque-agressive", apiUrl: "http://a" });
    expect(brand.css).toBe("");
    expect(describeFallback(brand)).toMatch(/^\[marque blanche\] repli sur le thème MulemaCare \(marque-agressive\) : contraste — light\.accent/);
    expect(describeFallback({ identity: null, theme: null, css: "", fallback: null })).toBeNull();
  });
});
