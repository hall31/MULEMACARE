/**
 * Gardes de design (AGENTS.md, Design ; POLISH_CONTRACT §2, §4, §5, §12) : aucune couleur littérale,
 * jetons du contrat seulement, six tailles de texte, aucun texte en dur, statuts et séries de
 * graphique sémantiques ou neutres (jamais l'accent), zones de 48 px, aucun CDN, aucun émoji.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import fr from "../../src/i18n/fr.json";
import { TONE_CLASSES, TONE_FILL } from "../../src/components/ui";
import { CONTRACT_STATUS_TONE } from "../../src/features/employer/employer-view";
import { MEMBER_STATUS_TONE } from "../../src/features/insurer/portfolio-view";

const here = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.resolve(here, "../../src");
const walk = (dir: string): string[] => readdirSync(dir).flatMap((n) => (statSync(path.join(dir, n)).isDirectory() ? walk(path.join(dir, n)) : [path.join(dir, n)]));
// Les mocks sont des données de démonstration, pas du code d'interface.
const code = walk(srcDir).filter((f) => /\.(tsx?|css)$/.test(f) && !f.endsWith(".d.ts") && !f.includes(`${path.sep}mocks${path.sep}`));
const read = (f: string) => readFileSync(f, "utf8");

describe("couleurs et jetons", () => {
  it("aucune couleur littérale (hexadécimale, rgb, hsl, oklch)", () => {
    const offenders = code.flatMap((f) => read(f).split("\n").map((l, i) => [l, i] as const).filter(([l]) => /#[0-9a-fA-F]{3,8}\b(?![-\w])|\brgba?\(|\bhsla?\(|\boklch\(/.test(l)).map(([l, i]) => `${path.relative(srcDir, f)}:${i + 1}: ${l.trim()}`));
    expect(offenders).toEqual([]);
  });

  it("jetons importés depuis le contrat ; palette et échelle Tailwind par défaut retirées", () => {
    const css = read(path.join(srcDir, "app/globals.css"));
    expect(css).toContain('@import "../../../../../specs/design/mulemacare-tokens.css";');
    expect(css).toContain("--color-*: initial;");
    expect(css).toContain("--text-*: initial;");
    for (const size of ["caption", "dense", "body", "title", "headline", "display"]) expect(css).toContain(`--text-${size}: var(--fs-${size});`);
  });

  it("aucune taille de texte arbitraire, aucun flou d'arrière-plan, aucune police distante, aucun émoji", () => {
    for (const f of code) {
      const text = read(f);
      expect(text, f).not.toMatch(/text-\[\d|backdrop-filter|backdrop-blur|fonts\.googleapis|fonts\.gstatic|next\/font\/google|[\u{1F300}-\u{1FAFF}✨✦]/u);
    }
    expect(JSON.stringify(fr)).not.toMatch(/[\u{1F300}-\u{1FAFF}✨✦]/u);
  });

  it("statuts et séries : ok / warn / crit / info / neutre, jamais l'accent", () => {
    for (const tone of [...Object.values(MEMBER_STATUS_TONE), ...Object.values(CONTRACT_STATUS_TONE)]) expect(["ok", "warn", "crit", "info", "neutral"]).toContain(tone);
    for (const cls of [...Object.values(TONE_CLASSES), ...Object.values(TONE_FILL)]) expect(cls).not.toMatch(/accent|brand/);
    expect(CONTRACT_STATUS_TONE.echu).toBe("crit");
    expect(CONTRACT_STATUS_TONE.a_echeance).toBe("warn");
  });
});

describe("textes", () => {
  it("aucun texte d'interface en dur dans les composants", () => {
    const offenders: string[] = [];
    const jsxText = /(?<![=\-])>\s*([A-Za-zÀ-ÿ][^<>{}()=&|;]*[A-Za-zÀ-ÿ.!?])\s*<\/?[A-Za-z]/;
    const literalAttr = /\b(aria-label|title|placeholder|alt)="[^"]*[A-Za-zÀ-ÿ]{2,}[^"]*"/;
    for (const f of code.filter((x) => x.endsWith(".tsx"))) {
      read(f).split("\n").forEach((line, i) => {
        if (line.trim().startsWith("//") || line.trim().startsWith("*")) return;
        if (jsxText.test(line) || literalAttr.test(line)) offenders.push(`${path.relative(srcDir, f)}:${i + 1}: ${line.trim()}`);
      });
    }
    expect(offenders).toEqual([]);
  });

  it("langue française et marque appliquée au rendu serveur", () => {
    const layout = read(path.join(srcDir, "app/layout.tsx"));
    expect(layout).toContain('lang="fr"');
    expect(layout).toContain("await getBrand()");
    expect(layout).toMatch(/<head>\s*<BrandStyle brand=\{brand\} \/>\s*<\/head>/);
  });
});

describe("mouvement, focus et cibles", () => {
  it("animations seulement sans réduction de mouvement ; focus visible sur jeton", () => {
    const css = read(path.join(srcDir, "app/globals.css"));
    expect(css.split("@media (prefers-reduced-motion: no-preference)")[0]).not.toMatch(/animation:|transition:/);
    expect(css).toMatch(/:focus-visible \{\s*outline: var\(--focus-w\) solid var\(--focus\);/);
  });

  it("boutons, liens de navigation et listes : 48 px (min-h-12)", () => {
    expect(read(path.join(srcDir, "components/ui.tsx"))).toContain("inline-flex min-h-12");
    for (const f of ["components/shell.tsx", "components/period-picker.tsx", "features/employer/employer-view.tsx"]) {
      const text = read(path.join(srcDir, f));
      for (const m of text.matchAll(/<(select|button)[^>]*className="([^"]+)"/g)) expect(m[2], `${f} ${m[1]}`).toContain("min-h-12");
    }
  });
});
