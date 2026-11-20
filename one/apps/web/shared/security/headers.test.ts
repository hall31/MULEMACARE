import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  HSTS,
  PERMISSIONS_POLICY,
  PROXY_EXCLUDED,
  contentSecurityPolicy,
  cspDirective,
  generateNonce,
  logoOrigins,
  originOf,
  staticSecurityHeaders,
  type AppKind,
} from "./headers";

const here = path.dirname(fileURLToPath(import.meta.url));
const APPS: AppKind[] = ["console", "counter", "member", "partner"];
const NONCE = "AAAAAAAAAAAAAAAAAAAAAA==";

describe("CSP stricte", () => {
  const prod = contentSecurityPolicy({ nonce: NONCE, dev: false });

  it("scripts et styles par nonce seulement, sans unsafe-inline ni unsafe-eval", () => {
    expect(cspDirective(prod, "script-src")).toEqual(["'self'", `'nonce-${NONCE}'`, "'strict-dynamic'"]);
    expect(cspDirective(prod, "style-src")).toEqual(["'self'", `'nonce-${NONCE}'`]);
    expect(prod).not.toContain("unsafe-eval");
    expect(prod.match(/'unsafe-inline'/g)).toHaveLength(1);
    expect(cspDirective(prod, "style-src-attr")).toEqual(["'unsafe-inline'"]);
  });

  it("aucun cadre, aucun plugin, aucune base réécrite", () => {
    expect(cspDirective(prod, "frame-ancestors")).toEqual(["'none'"]);
    expect(cspDirective(prod, "frame-src")).toEqual(["'none'"]);
    expect(cspDirective(prod, "object-src")).toEqual(["'none'"]);
    expect(cspDirective(prod, "base-uri")).toEqual(["'none'"]);
    expect(cspDirective(prod, "form-action")).toEqual(["'self'"]);
    expect(cspDirective(prod, "default-src")).toEqual(["'self'"]);
  });

  it("développement : unsafe-eval (React) et WebSocket (rechargement à chaud) seulement là", () => {
    const dev = contentSecurityPolicy({ nonce: NONCE, dev: true });
    expect(cspDirective(dev, "script-src")).toContain("'unsafe-eval'");
    expect(cspDirective(dev, "connect-src")).toEqual(["'self'", "ws:", "wss:"]);
    expect(cspDirective(prod, "connect-src")).toEqual(["'self'"]);
  });

  it("origines supplémentaires : seulement des origines exactes, logos en https", () => {
    const csp = contentSecurityPolicy({
      nonce: NONCE,
      dev: false,
      connect: ["http://localhost:8000", "https://api.exemple.ci/v1", "*", "javascript:alert(1)"],
      images: ["https://logos.exemple.ci", "http://logos.exemple.ci", "data:"],
    });
    expect(cspDirective(csp, "connect-src")).toEqual(["'self'", "http://localhost:8000"]);
    expect(cspDirective(csp, "img-src")).toEqual(["'self'", "data:", "blob:", "https://logos.exemple.ci"]);
  });

  it("refuse un nonce absent ou injectable", () => {
    expect(() => contentSecurityPolicy({ nonce: "", dev: false })).toThrow();
    expect(() => contentSecurityPolicy({ nonce: "abc' 'unsafe-inline", dev: false })).toThrow();
  });

  it("nonce de 128 bits, différent à chaque appel", () => {
    const nonces = new Set(Array.from({ length: 200 }, generateNonce));
    expect(nonces.size).toBe(200);
    for (const nonce of nonces) expect(atob(nonce)).toHaveLength(16);
  });
});

describe("origines", () => {
  it("originOf ne garde que http(s), sans identifiants", () => {
    expect(originOf("http://localhost:8000/")).toBe("http://localhost:8000");
    expect(originOf("https://api.exemple.ci/v1?x=1")).toBe("https://api.exemple.ci");
    expect(originOf("https://u:p@api.exemple.ci")).toBeNull();
    expect(originOf("ftp://x")).toBeNull();
    expect(originOf("pas une url")).toBeNull();
    expect(originOf(undefined)).toBeNull();
  });

  it("logoOrigins : hôtes valides en https, le reste ignoré", () => {
    expect(logoOrigins(" Logos.Exemple.ci, *.evil.example, https://x.y, cdn.exemple.sn ,")).toEqual([
      "https://logos.exemple.ci",
      "https://cdn.exemple.sn",
    ]);
    expect(logoOrigins(undefined)).toEqual([]);
  });
});

describe("en-têtes statiques", () => {
  it.each(APPS)("%s : nosniff, no-referrer, DENY, COOP, Permissions-Policy, HSTS en production", (app) => {
    const prod = Object.fromEntries(staticSecurityHeaders(app, { production: true }).map((h) => [h.key, h.value]));
    expect(prod).toMatchObject({
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
      "X-Frame-Options": "DENY",
      "Cross-Origin-Opener-Policy": "same-origin",
      "Strict-Transport-Security": HSTS,
      "Permissions-Policy": PERMISSIONS_POLICY[app],
    });
    const dev = staticSecurityHeaders(app, { production: false }).map((h) => h.key);
    expect(dev).not.toContain("Strict-Transport-Security");
  });

  it("seul le comptoir a la caméra ; personne n'a micro ni géolocalisation", () => {
    for (const app of APPS) {
      expect(PERMISSIONS_POLICY[app]).toContain("microphone=()");
      expect(PERMISSIONS_POLICY[app]).toContain("geolocation=()");
      expect(PERMISSIONS_POLICY[app]).toContain(app === "counter" ? "camera=(self)" : "camera=()");
    }
  });
});

describe("chaque app branche les en-têtes", () => {
  it.each(APPS)("%s : proxy.ts avec la CSP partagée et le matcher partagé", (app) => {
    const proxy = readFileSync(path.join(here, `../../${app}/src/proxy.ts`), "utf8");
    expect(proxy).toContain("contentSecurityPolicy(");
    expect(proxy).toContain(`source: "/((?!${PROXY_EXCLUDED}).*)"`);
    const config = readFileSync(path.join(here, `../../${app}/next.config.ts`), "utf8");
    expect(config).toContain(`staticSecurityHeaders("${app}"`);
    const brandStyle = readFileSync(path.join(here, `../../${app}/src/brand/brand-style.tsx`), "utf8");
    expect(brandStyle).toContain("nonce={nonce}");
  });
});
