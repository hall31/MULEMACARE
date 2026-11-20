import { expect, test, type APIResponse, type Page } from "@playwright/test";
import { BRANDING_FIXTURES, BRAND_FIXTURE_COOKIE } from "../../shared/brand/index";
import { HSTS, PERMISSIONS_POLICY, cspDirective } from "../../shared/security/headers";
import { openCounter, toIdentity } from "./flow";

/**
 * En-têtes de sécurité RÉELLEMENT servis par `next start` (phase 4, voie 2) et parcours du comptoir
 * sous la CSP stricte : aucune violation remontée par le navigateur.
 */

declare global {
  interface Window {
    __cspViolations?: string[];
  }
}

async function watchCsp(page: Page): Promise<() => Promise<string[]>> {
  await page.addInitScript(() => {
    window.__cspViolations = [];
    document.addEventListener("securitypolicyviolation", (event) => {
      window.__cspViolations?.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  const console: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && /content security policy|refused to/i.test(message.text())) console.push(message.text());
  });
  return async () => [...(await page.evaluate(() => window.__cspViolations ?? [])), ...console];
}

function nonceOf(response: APIResponse): string {
  const csp = response.headers()["content-security-policy"] ?? "";
  const nonce = cspDirective(csp, "script-src")?.find((s) => s.startsWith("'nonce-"));
  expect(nonce, "nonce dans script-src").toBeDefined();
  return nonce!.slice("'nonce-".length, -1);
}

test("document : CSP stricte à nonce, HSTS, nosniff, no-referrer, DENY, caméra pour le comptoir seul", async ({ request }) => {
  const response = await request.get("/");
  expect(response.ok()).toBe(true);
  const headers = response.headers();
  const csp = headers["content-security-policy"] ?? "";
  expect(cspDirective(csp, "script-src")).toEqual(expect.arrayContaining(["'self'", "'strict-dynamic'"]));
  expect(cspDirective(csp, "script-src")).not.toContain("'unsafe-inline'");
  expect(cspDirective(csp, "style-src")).not.toContain("'unsafe-inline'");
  expect(csp).not.toContain("unsafe-eval");
  expect(cspDirective(csp, "frame-ancestors")).toEqual(["'none'"]);
  expect(cspDirective(csp, "object-src")).toEqual(["'none'"]);
  expect(headers["strict-transport-security"]).toBe(HSTS);
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("no-referrer");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["permissions-policy"]).toBe(PERMISSIONS_POLICY.counter);
  expect(headers["x-powered-by"]).toBeUndefined();

  // Next.js pose le nonce de la requête sur ses scripts ; un nonce neuf à chaque requête.
  const nonce = nonceOf(response);
  const html = await response.text();
  const scripts = [...html.matchAll(/<script\b[^>]*>/g)].map((m) => m[0]);
  expect(scripts.length).toBeGreaterThan(0);
  for (const tag of scripts) expect(tag).toContain(`nonce="${nonce}"`);
  expect(nonceOf(await request.get("/"))).not.toBe(nonce);
});

test("fichiers statiques : nosniff et no-referrer aussi", async ({ request }) => {
  const html = await (await request.get("/")).text();
  const src = /<script[^>]+src="(\/_next\/static\/[^"]+\.js)"/.exec(html)?.[1];
  expect(src).toBeDefined();
  const asset = await request.get(src!);
  expect(asset.headers()["x-content-type-options"]).toBe("nosniff");
  expect(asset.headers()["referrer-policy"]).toBe("no-referrer");
  const sw = await request.get("/sw.js");
  expect(sw.headers()["x-content-type-options"]).toBe("nosniff");
});

test("le comptoir fonctionne sous la CSP : accueil puis identification, aucune violation", async ({ page }) => {
  const violations = await watchCsp(page);
  await openCounter(page);
  await toIdentity(page);
  expect(await violations()).toEqual([]);
});

test("marque blanche sous la CSP : le style de la marque porte le nonce et s'applique", async ({ page, context, baseURL }) => {
  const slug = "lagune-sante";
  await context.addCookies([{ name: BRAND_FIXTURE_COOKIE, value: slug, url: baseURL! }]);
  const violations = await watchCsp(page);
  await openCounter(page);
  const accent = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--accent").trim());
  expect(accent).toBe(BRANDING_FIXTURES[slug]!.theme.light!.accent);
  expect(await violations()).toEqual([]);
});
