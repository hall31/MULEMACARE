import AxeBuilder from "@axe-core/playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";
import { t } from "../../src/i18n";
import type { DemoRole } from "../../src/lib/session";

const here = path.dirname(fileURLToPath(import.meta.url));
export const screenshotsDir = path.resolve(here, "../../screenshots");

/** Ouvre un espace avec le profil de démonstration (remplace la connexion en mode mock). */
export async function openAs(page: Page, role: DemoRole, url: string): Promise<void> {
  await page.addInitScript((r) => window.localStorage.setItem("mulemacare-one.partenaires.demo-role", r), role);
  await page.goto(url);
  await expect(page.getByTestId("current-role")).toHaveText(t(`roles.${role}`));
}

export async function axe(page: Page): Promise<string[]> {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
  return results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 4).join(", ")}`);
}

/** Débordement horizontal (contrat §11 : 0 px à 375, 768, 1280). */
export const overflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);

/** Contrôles visibles sous 48 px (zones tactiles des espaces partenaires). */
export async function smallTargets(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll("button, select, summary, nav a, input")]
      .filter((el) => (el as HTMLElement).offsetParent !== null)
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.height < 48)
      .map(({ el, r }) => `${el.tagName.toLowerCase()} ${Math.round(r.height)}px ${(el.textContent ?? "").trim().slice(0, 30)}`),
  );
}

export async function shot(page: Page, name: string): Promise<void> {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(screenshotsDir, `${name}.png`), fullPage: true });
}
