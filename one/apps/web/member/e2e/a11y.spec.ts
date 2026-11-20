import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { SCREEN_NAMES, SCREENS } from "./screens";

/** axe-core, WCAG 2.0 / 2.1 / 2.2 niveaux A et AA, sur chaque écran et chaque état, en clair et en sombre. */
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function audit(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return results.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.map((n) => n.target.join(" ")).slice(0, 5) }));
}

for (const mode of ["clair", "sombre"] as const) {
  test.describe(`axe AA — ${mode}`, () => {
    test.use({ colorScheme: mode === "sombre" ? "dark" : "light" });
    for (const name of SCREEN_NAMES) {
      test(name, async ({ page, context }) => {
        await SCREENS[name](page, context);
        // Animations signature terminées (cachet) avant l'audit des contrastes.
        await page.waitForTimeout(450);
        expect(await audit(page)).toEqual([]);
      });
    }
  });
}
