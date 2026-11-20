import { expect, test } from "@playwright/test";
import { SCREEN_NAMES, SCREENS } from "./screens";

/**
 * R12 — mesures réelles dans le navigateur, sur chaque écran :
 * zones tactiles ≥ 48 px, bouton principal 56 px dans la barre du bas, texte ≥ 16 px.
 */
const INTERACTIVE = 'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [role="switch"], [tabindex]:not([tabindex="-1"])';

for (const name of SCREEN_NAMES) {
  test(`zones tactiles et texte — ${name}`, async ({ page, context }) => {
    await SCREENS[name](page, context);

    const targets = await page.locator(INTERACTIVE).evaluateAll((elements) =>
      elements
        .filter((el) => (el as HTMLElement).offsetParent !== null || getComputedStyle(el).position === "fixed")
        .map((el) => {
          const box = el.getBoundingClientRect();
          return { label: (el.getAttribute("aria-label") ?? el.textContent ?? el.id).trim().slice(0, 50), width: box.width, height: box.height };
        }),
    );
    expect(targets.length).toBeGreaterThan(0);
    for (const target of targets) {
      expect.soft(target.height, `hauteur de « ${target.label} »`).toBeGreaterThanOrEqual(48);
      expect.soft(target.width, `largeur de « ${target.label} »`).toBeGreaterThanOrEqual(48);
    }

    // Bouton principal : 56 px, dans la barre d'actions collée au bas de l'écran.
    const footer = page.getByTestId("counter-footer");
    const primary = footer.locator('button[data-variant="primary"]').first();
    const primaryBox = await primary.boundingBox();
    const footerBox = await footer.boundingBox();
    const viewport = page.viewportSize();
    expect(primaryBox?.height ?? 0).toBeGreaterThanOrEqual(56);
    expect(footerBox && viewport ? Math.round(footerBox.y + footerBox.height) : -1).toBe(viewport?.height);

    // Texte : 16 px minimum pour tout nœud texte visible.
    const small = await page.evaluate(() => {
      const found: string[] = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const text = node.textContent?.trim();
        const parent = node.parentElement;
        if (!text || !parent || parent.closest(".sr-only, [aria-hidden='true'], script, style")) continue;
        if (parent.getClientRects().length === 0) continue;
        const size = parseFloat(getComputedStyle(parent).fontSize);
        if (size < 16) found.push(`${text.slice(0, 40)} (${size}px)`);
      }
      return found;
    });
    expect(small, "textes sous 16 px").toEqual([]);
  });
}
