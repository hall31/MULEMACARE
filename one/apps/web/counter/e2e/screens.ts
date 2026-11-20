import { expect, type BrowserContext, type Page } from "@playwright/test";
import { MockApi } from "./mock-api";
import { fr, openCounter, selectActs, toActs, toCode, toIdentity } from "./flow";

/** Amène le comptoir sur chacun des cinq écrans (plus la variante hors ligne de la décision). */
export const SCREENS = {
  carte: async (page: Page) => {
    await openCounter(page);
  },
  identite: async (page: Page) => {
    await openCounter(page);
    await toIdentity(page);
  },
  code: async (page: Page) => {
    await openCounter(page);
    await toCode(page);
  },
  actes: async (page: Page) => {
    await openCounter(page);
    await toActs(page);
    await selectActs(page, ["CS-GEN", "NFS", "ECG"]);
  },
  decision: async (page: Page) => {
    await openCounter(page);
    await toActs(page);
    await selectActs(page, ["CS-GEN", "NFS", "ECG"]);
    await page.getByRole("button", { name: fr["acts.submit"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.auto"] })).toBeVisible();
  },
  "carte-aide": async (page: Page) => {
    const api = new MockApi();
    api.coachMarks = true;
    await openCounter(page, api);
    await expect(page.getByTestId("coach-mark")).toBeVisible();
  },
  "actes-aide": async (page: Page) => {
    const api = new MockApi();
    api.coachMarks = true;
    await openCounter(page, api);
    await toActs(page);
    await expect(page.getByTestId("coach-mark")).toHaveAttribute("data-step", "acts");
  },
  "carte-hors-ligne": async (page: Page, context: BrowserContext) => {
    const api = await openCounter(page);
    api.networkDown = true;
    await context.setOffline(true);
    await expect(page.getByTestId("offline-cannot").first()).toBeVisible();
  },
  "actes-hors-ligne": async (page: Page, context: BrowserContext) => {
    const api = await openCounter(page);
    await toActs(page);
    api.networkDown = true;
    await context.setOffline(true);
    await selectActs(page, ["CS-GEN"]);
    await expect(page.getByTestId("offline-can").first()).toBeVisible();
  },
  "decision-hors-ligne": async (page: Page, context: BrowserContext) => {
    const api = new MockApi();
    await openCounter(page, api);
    await toActs(page);
    api.networkDown = true;
    await context.setOffline(true);
    await selectActs(page, ["CS-GEN", "NFS", "ECG"]);
    await page.getByRole("button", { name: fr["acts.submit"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.provisional"] })).toBeVisible();
  },
} satisfies Record<string, (page: Page, context: BrowserContext) => Promise<void>>;

export type ScreenName = keyof typeof SCREENS;
export const SCREEN_NAMES = Object.keys(SCREENS) as ScreenName[];
