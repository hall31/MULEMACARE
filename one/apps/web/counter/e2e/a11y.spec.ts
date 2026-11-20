import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { SCREEN_NAMES, SCREENS } from "./screens";

/** `make a11y` : axe-core, WCAG 2.0 / 2.1 / 2.2 niveaux A et AA, sur chaque écran et chaque thème. */
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

type Mode = "clair" | "sombre" | "plein-soleil";
const MODES: Mode[] = ["clair", "sombre", "plein-soleil"];

async function audit(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return results.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map((n) => n.target.join(" ")).slice(0, 5) }));
}

for (const mode of MODES) {
  test.describe(`axe AA — ${mode}`, () => {
    test.use({ colorScheme: mode === "sombre" ? "dark" : "light" });
    for (const name of SCREEN_NAMES) {
      test(name, async ({ page, context }) => {
        if (mode === "plein-soleil") await page.addInitScript(() => window.localStorage.setItem("mulema.sun", "1"));
        await SCREENS[name](page, context);
        if (mode === "plein-soleil") await expect(page.locator("html")).toHaveAttribute("data-sun", "");
        expect(await audit(page)).toEqual([]);
      });
    }
  });
}
