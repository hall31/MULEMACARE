/**
 * Garde-fous de design (AGENTS.md, Design ; LOTS.md L6 « aucune couleur en dur ») :
 * - aucune couleur littérale (hexadécimale, rgb(), hsl()) dans le code de la console ;
 * - les jetons viennent du fichier contrat specs/design/mulemacare-tokens.css ;
 * - aucun texte d'interface en dur dans les composants (tout passe par fr.json) ;
 * - les statuts utilisent les couleurs sémantiques, jamais l'accent de marque.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { cn } from "../../src/lib/cn";
import { CLAIM_STATUS_TONE, CONTRIBUTION_STATUS_TONE, MEMBER_STATUS_TONE, PLAN_VERSION_TONE, TONE_CLASSES } from "../../src/lib/status";

const here = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.resolve(here, "../../src");

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

const codeFiles = walk(srcDir).filter((f) => /\.(tsx?|css)$/.test(f) && !f.endsWith(".d.ts"));

describe("couleurs", () => {
  it("aucune couleur littérale dans src/", () => {
    const offenders: string[] = [];
    const literal = /#[0-9a-fA-F]{3,8}\b(?![-\w])|\brgba?\(|\bhsla?\(|\boklch\(\s*\d/;
    for (const file of codeFiles) {
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (literal.test(line)) offenders.push(`${path.relative(srcDir, file)}:${i + 1}: ${line.trim()}`);
        });
    }
    expect(offenders).toEqual([]);
  });

  it("les jetons sont importés depuis le contrat specs/design", () => {
    const css = readFileSync(path.join(srcDir, "app/globals.css"), "utf8");
    expect(css).toContain('@import "../../../../../specs/design/mulemacare-tokens.css";');
    const tokens = path.resolve(srcDir, "app", "../../../../../specs/design/mulemacare-tokens.css");
    expect(readFileSync(tokens, "utf8")).toContain("--accent:");
  });

  it("aucune police chargée depuis un CDN", () => {
    for (const file of codeFiles) {
      expect(readFileSync(file, "utf8"), file).not.toMatch(/fonts\.googleapis|fonts\.gstatic|next\/font\/google/);
    }
  });
});

describe("statuts", () => {
  const all = [CLAIM_STATUS_TONE, MEMBER_STATUS_TONE, CONTRIBUTION_STATUS_TONE, PLAN_VERSION_TONE];

  it("chaque statut a un ton sémantique, jamais l'accent", () => {
    for (const map of all) {
      for (const tone of Object.values(map)) {
        expect(["ok", "warn", "crit", "neutral"]).toContain(tone);
      }
    }
  });

  it("les classes des tons n'utilisent pas les couleurs de marque", () => {
    for (const cls of Object.values(TONE_CLASSES)) {
      expect(cls).not.toMatch(/brand|primary|accent/);
    }
  });

  it("revue et refus sont distingués sémantiquement", () => {
    expect(CLAIM_STATUS_TONE.en_revue).toBe("warn");
    expect(CLAIM_STATUS_TONE.refusee).toBe("crit");
    expect(CLAIM_STATUS_TONE.accordee).toBe("ok");
    expect(CLAIM_STATUS_TONE.accordee_auto).toBe("ok");
  });
});

describe("textes", () => {
  it("aucun texte d'interface en dur dans les composants", () => {
    const offenders: string[] = [];
    // Texte JSX entre une fin de balise et une balise suivante (hors flèches « => » et comparaisons).
    const jsxText = /(?<![=\-])>\s*([A-Za-zÀ-ÿ][^<>{}()=&|;]*[A-Za-zÀ-ÿ.!?])\s*<\/?[A-Za-z]/;
    // Attributs d'accessibilité ou d'aide écrits en dur.
    const literalAttr = /\b(aria-label|title|placeholder|alt)="[^"]*[A-Za-zÀ-ÿ]{2,}[^"]*"/;
    for (const file of codeFiles.filter((f) => f.endsWith(".tsx"))) {
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (line.trim().startsWith("//") || line.trim().startsWith("*")) return;
          if (jsxText.test(line) || literalAttr.test(line)) {
            offenders.push(`${path.relative(srcDir, file)}:${i + 1}: ${line.trim()}`);
          }
        });
    }
    expect(offenders).toEqual([]);
  });
});

describe("échelle de texte (POLISH_CONTRACT §4 : six tailles, pas une de plus)", () => {
  // Composants ajoutés en Phase 2 et suivants : tailles par jetons seulement.
  const TOKENIZED = [
    "features/palette/command-palette.tsx",
    "features/metrics/metrics-view.tsx",
    "components/measure-consent.tsx",
    // Phase 3 : marque blanche et accueil d'organisation.
    "features/branding/branding-view.tsx",
    "features/platform/organizations-view.tsx",
    "features/home/home-gate.tsx",
    "components/form-field.tsx",
  ];
  const SCALE = ["caption", "dense", "body", "title", "headline", "display"];

  it("chaque jeton de taille du contrat est exposé à Tailwind (text-caption … text-display)", () => {
    const css = readFileSync(path.join(srcDir, "app/globals.css"), "utf8");
    for (const size of SCALE) {
      expect(css).toContain(`--text-${size}: var(--fs-${size});`);
      expect(css).toContain(`--text-${size}--line-height: var(--lh-${size});`);
    }
  });

  it("aucune taille en pixels arbitraires ni taille Tailwind hors jetons dans ces composants", () => {
    const offenders: string[] = [];
    const arbitrary = /\btext-\[\d+(?:\.\d+)?(?:px|rem)\]|\btext-(?:xs|sm|base|lg|xl|[2-9]xl)\b/;
    for (const rel of TOKENIZED) {
      readFileSync(path.join(srcDir, rel), "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (arbitrary.test(line)) offenders.push(`${rel}:${i + 1}: ${line.trim()}`);
        });
    }
    expect(offenders).toEqual([]);
  });

  it("cn() garde la taille par jeton à côté d'une couleur de texte (tailwind-merge ne les confond pas)", () => {
    for (const size of SCALE) {
      expect(cn(`p-2 text-${size}`, "text-fg-2").split(" ")).toEqual(expect.arrayContaining([`text-${size}`, "text-fg-2"]));
    }
    expect(cn("text-caption", "text-dense")).toBe("text-dense");
  });

  it("le surtitre (eyebrow) suit le jeton de légende (12 px), pas 11 px", () => {
    const css = readFileSync(path.join(srcDir, "app/globals.css"), "utf8");
    const eyebrow = css.slice(css.indexOf("@utility eyebrow"), css.indexOf("}", css.indexOf("@utility eyebrow")));
    expect(eyebrow).toContain("font-size: var(--fs-caption);");
  });
});

describe("marque blanche (P3)", () => {
  it("le layout lit la marque avant le premier rendu et ne sert que le CSS de la liste fermée", () => {
    const layout = readFileSync(path.join(srcDir, "app/layout.tsx"), "utf8");
    expect(layout).toMatch(/export default async function RootLayout/);
    expect(layout).toContain("await getBrand()");
    expect(layout).toMatch(/<head>\s*<BrandStyle brand=\{brand\} \/>\s*<\/head>/);
    const style = readFileSync(path.join(srcDir, "brand/brand-style.tsx"), "utf8");
    expect(style).toContain("__html: brand.css");
    const server = readFileSync(path.join(srcDir, "brand/brand.server.ts"), "utf8");
    // Le cookie de choix d'organisation n'est lu qu'en démonstration.
    expect(server).toMatch(/FIXTURES \? \(\(await cookies\(\)\)/);
  });

  it("le logo n'est rendu qu'en image (jamais en HTML)", () => {
    for (const file of codeFiles) expect(readFileSync(file, "utf8"), file).not.toMatch(/dangerouslySetInnerHTML=\{\{ __html: (?!brand\.css)/);
  });
});

describe("mouvement et focus", () => {
  it("les animations sont conditionnées à prefers-reduced-motion", () => {
    const css = readFileSync(path.join(srcDir, "app/globals.css"), "utf8");
    expect(css).toContain("@media (prefers-reduced-motion: no-preference)");
    expect(css).toContain("@media (prefers-reduced-motion: reduce)");
    const animationOutside = css
      .split("@media (prefers-reduced-motion: no-preference)")[0]!
      .match(/animation:\s*mc-/);
    expect(animationOutside).toBeNull();
  });

  it("un focus visible est défini pour tous les contrôles", () => {
    const css = readFileSync(path.join(srcDir, "app/globals.css"), "utf8");
    expect(css).toMatch(/:focus-visible\s*\{\s*outline: 2px solid var\(--accent\)/);
  });
});
