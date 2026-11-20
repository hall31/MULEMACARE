import { expect, test } from "@playwright/test";
import { FORBIDDEN_TEXT } from "./flow";
import { SCREEN_NAMES, SCREENS } from "./screens";

/**
 * Surface « comptoir » de l'espace adhérent (AGENTS.md, contrat §9 et §11), mesurée dans le
 * navigateur sur chaque écran : zones tactiles ≥ 48 px, action principale ≥ 56 px, texte ≥ 16 px,
 * aucun débordement horizontal, aucune donnée médicale ni score affichés.
 */
/** Fins de parcours du payeur : rien à faire de plus (payé, lien expiré, lien inconnu). */
const TERMINAL = new Set(["paiement-confirme", "paiement-expire", "paiement-invalide"]);

const INTERACTIVE = 'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [tabindex]:not([tabindex="-1"])';

for (const name of SCREEN_NAMES) {
  test(`zones tactiles, texte et contenu — ${name}`, async ({ page, context }) => {
    await SCREENS[name](page, context);

    const targets = await page.locator(INTERACTIVE).evaluateAll((elements) =>
      elements
        .filter((el) => (el as HTMLElement).offsetParent !== null || getComputedStyle(el).position === "fixed")
        .filter((el) => !el.classList.contains("skip"))
        .map((el) => {
          // Un bouton radio se touche par toute son étiquette.
          const target = el instanceof HTMLInputElement && el.type === "radio" ? (el.closest("label") ?? el) : el;
          const box = target.getBoundingClientRect();
          return { label: (el.getAttribute("aria-label") ?? target.textContent ?? el.id).trim().slice(0, 50), width: box.width, height: box.height };
        }),
    );
    if (!TERMINAL.has(name)) expect(targets.length).toBeGreaterThan(0);
    for (const target of targets) {
      expect.soft(target.height, `hauteur de « ${target.label} »`).toBeGreaterThanOrEqual(48);
      expect.soft(target.width, `largeur de « ${target.label} »`).toBeGreaterThanOrEqual(48);
    }

    // Action principale : 56 px, une seule par écran.
    const primaries = page.locator('[data-variant="primary"]:visible');
    expect(await primaries.count(), "une seule action principale").toBeLessThanOrEqual(1);
    for (const box of await primaries.evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height))) expect(box).toBeGreaterThanOrEqual(56);

    const small = await page.evaluate(() => {
      const found: string[] = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const text = node.textContent?.trim();
        const parent = node.parentElement;
        if (!text || !parent || parent.closest(".sr-only, [aria-hidden='true'], script, style, .skip")) continue;
        if (parent.getClientRects().length === 0) continue;
        const size = parseFloat(getComputedStyle(parent).fontSize);
        if (size < 16) found.push(`${text.slice(0, 40)} (${size}px)`);
      }
      return found;
    });
    expect(small, "textes sous 16 px").toEqual([]);

    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth), "débordement horizontal à 375 px").toBeLessThanOrEqual(0);
    await expect(page.locator("body")).not.toContainText(FORBIDDEN_TEXT);
  });
}

test.describe("aucun débordement horizontal à 768 et 1280 px", () => {
  for (const width of [768, 1280]) {
    for (const name of ["carte", "soins", "suivi", "cotisations", "famille", "paiement"] as const) {
      test(`${name} — ${width} px`, async ({ page, context }) => {
        await page.setViewportSize({ width, height: 900 });
        await SCREENS[name](page, context);
        expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
        if (name !== "paiement") {
          // Navigation dans la barre du haut au-delà de 768 px, barre d'onglets en dessous.
          await expect(page.getByTestId("tabbar")).toBeHidden();
          await expect(page.getByRole("navigation", { name: /Espace adhérent/ }).first()).toBeVisible();
        }
      });
    }
  }
});
