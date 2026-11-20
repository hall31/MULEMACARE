// Captures et audit de la planche « Registre émeraude ».
// Usage : node specs/design/direction/capture.mjs   (depuis one/, après `pnpm install` de la console)
// Réutilise Playwright et axe-core déjà installés pour apps/web/console : aucune dépendance ajoutée.
// Sortie : screenshots/*.png ; code de sortie 1 si axe (WCAG 2.2 A/AA) ou un débordement horizontal échoue.
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.resolve(here, "../../../apps/web/console/package.json"));
const { chromium } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

const page_url = pathToFileURL(path.join(here, "index.html")).href;
const out = path.join(here, "screenshots");
mkdirSync(out, { recursive: true });

const SCREENS = [
  ["comptoir", "01-comptoir-decision"],
  ["revue", "02-console-file-de-revue"],
  ["adherent", "03-espace-adherent-carte"],
  ["paiement", "04-lien-paiement-diaspora"],
  ["grand-livre", "05-console-grand-livre"],
];
const VIEWPORTS = { 375: 812, 768: 1024, 1280: 800 };
const THEMES = { clair: "light", sombre: "dark" };
const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

const failures = [];
const browser = await chromium.launch();

async function shoot({ query, width, file, audit, fold = false }) {
  const context = await browser.newContext({ viewport: { width, height: VIEWPORTS[width] ?? 900 }, reducedMotion: "reduce", deviceScaleFactor: 1 });
  const page = await context.newPage();
  await page.goto(`${page_url}?${query}`);
  await page.evaluate(() => document.fonts.ready);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 0) failures.push(`${file} : débordement horizontal de ${overflow} px`);
  // En mode écran, l'application doit occuper toute la largeur (sinon le responsive n'est pas testé).
  const gap = await page.evaluate(() => {
    const app = document.querySelector(".is-target .app");
    return app ? Math.round(window.innerWidth - app.getBoundingClientRect().width) : 0;
  });
  if (gap > 0) failures.push(`${file} : l'écran n'occupe pas toute la largeur (${gap} px manquants)`);
  if (audit) {
    const { violations } = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    for (const v of violations) failures.push(`${file} : axe ${v.id} (${v.nodes.length}) ${v.help}`);
  }
  await page.screenshot({ path: path.join(out, `${file}.png`), fullPage: !fold });
  await context.close();
}

for (const [id, name] of SCREENS) {
  for (const [label, theme] of Object.entries(THEMES)) {
    for (const width of Object.keys(VIEWPORTS).map(Number)) {
      await shoot({ query: `screen=${id}&theme=${theme}&static=1`, width, file: `${name}-${width}-${label}`, audit: true });
    }
  }
}
for (const [id, name] of SCREENS.filter(([id]) => ["comptoir", "adherent", "paiement"].includes(id))) {
  await shoot({ query: `screen=${id}&sun=1&static=1`, width: 375, file: `${name}-375-plein-soleil`, audit: true });
}
// Pli du téléphone : ce que voit le comptoir sans défiler, action principale collée en bas.
for (const [id, name] of SCREENS.filter(([id]) => ["comptoir", "adherent"].includes(id))) {
  await shoot({ query: `screen=${id}&theme=light`, width: 375, file: `${name}-375-pli`, audit: false, fold: true });
}
for (const [label, theme] of Object.entries(THEMES)) {
  await shoot({ query: `theme=${theme}`, width: 1440, file: `00-planche-1440-${label}`, audit: true });
}
await browser.close();

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log(`ok : ${SCREENS.length * 6 + 7} captures, axe WCAG 2.2 AA sans violation, aucun débordement horizontal`);
