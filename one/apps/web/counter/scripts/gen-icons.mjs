// Génère les icônes PWA à partir des jetons de design (specs/design/mulemacare-tokens.css).
// Usage : node scripts/gen-icons.mjs — outil de développement, résultat versionné dans public/icons.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));
const tokens = readFileSync(path.join(here, "../../../../specs/design/mulemacare-tokens.css"), "utf8");
const out = path.join(here, "../public/icons");

const icons = [
  { file: "icon-192.png", size: 192, inset: 0, radius: 0.22 },
  { file: "icon-512.png", size: 512, inset: 0, radius: 0.22 },
  // Maskable : le motif tient dans la zone sûre (80 % central).
  { file: "icon-maskable-512.png", size: 512, inset: 0, radius: 0, glyph: 0.42 },
];

const browser = await chromium.launch();
const page = await browser.newPage({ colorScheme: "light" });
for (const icon of icons) {
  const glyph = Math.round(icon.size * (icon.glyph ?? 0.58));
  await page.setViewportSize({ width: icon.size, height: icon.size });
  await page.setContent(`<!doctype html><html data-theme="light"><head><style>${tokens}
    html,body{margin:0;background:transparent}
    .i{width:${icon.size}px;height:${icon.size}px;display:grid;place-items:center;background:var(--accent);color:var(--accent-fg);
       border-radius:${Math.round(icon.size * icon.radius)}px;font:700 ${glyph}px var(--f-display);letter-spacing:-0.02em}
  </style></head><body><div class="i">M</div></body></html>`);
  await page.locator(".i").screenshot({ path: path.join(out, icon.file), omitBackground: true });
}
await browser.close();
console.log("icônes générées dans", out);
