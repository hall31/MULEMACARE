import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, type Page } from "@playwright/test";
import { t } from "../../src/i18n";

export type { DemoRole } from "../../src/lib/session";
import type { DemoRole } from "../../src/lib/session";

const here = path.dirname(fileURLToPath(import.meta.url));
export const screenshotsDir = path.resolve(here, "../../screenshots");

export const MEASURE_CHOICE_KEY = "mulemacare-one.console.mesure.choix";
export type MeasureSetup = "unset" | "granted" | "refused";

/**
 * Ouvre la console et choisit le profil de démonstration (remplace la connexion en mode mock).
 * Mesure d'usage : les parcours qui ne la testent pas jouent une personne qui a déjà refusé (pas
 * de bandeau de premier usage) ; « unset » laisse le navigateur vierge. Le choix n'est posé que
 * s'il n'existe pas : un clic du test le remplace pour la suite du parcours.
 */
export async function openAs(page: Page, role: DemoRole, url = "/", measure: MeasureSetup = "refused"): Promise<void> {
  if (measure !== "unset") {
    await page.addInitScript(
      ([key, choice]) => {
        try {
          if (!window.localStorage.getItem(key)) window.localStorage.setItem(key, JSON.stringify({ v: 1, choice }));
        } catch {
          // Stockage indisponible : rien à poser.
        }
      },
      [MEASURE_CHOICE_KEY, measure] as const,
    );
  }
  await page.goto(url);
  const profile = page.getByLabel(t("session.demoProfile"));
  await expect(profile).toBeVisible();
  if ((await profile.inputValue()) !== role) {
    await profile.selectOption(role);
  }
  await expect(page.getByTestId("current-role")).toHaveText(t(`roles.${role}`));
}

export async function goToClaims(page: Page): Promise<void> {
  await page
    .getByRole("navigation", { name: t("nav.label") })
    .getByRole("link", { name: new RegExp(`^${t("nav.claims")}`) })
    .click();
  await expect(page.getByRole("heading", { level: 1, name: t("claims.title") })).toBeVisible();
}

export async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: path.join(screenshotsDir, `${name}.png`), fullPage: false });
}
