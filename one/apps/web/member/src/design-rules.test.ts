import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import fr from "./i18n/fr.json";

/** Garde des jetons et des textes (AGENTS.md « Design », docs/POLISH_CONTRACT.md §2, §4, §12). */
const here = path.dirname(fileURLToPath(import.meta.url));

function files(dir: string, ext: RegExp): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return files(full, ext);
    return ext.test(name) && !name.endsWith(".test.ts") && !name.endsWith(".d.ts") ? [full] : [];
  });
}

const sources = [...files(here, /\.(tsx?|css)$/), path.join(here, "../public/sw.js")].map((file) => ({
  file: path.relative(path.join(here, ".."), file),
  text: readFileSync(file, "utf8"),
}));

describe("règles de design de l'espace adhérent", () => {
  it("aucune couleur en dur : uniquement les jetons", () => {
    const offenders = sources.filter(({ text }) => /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(/.test(text)).map((s) => s.file);
    expect(offenders).toEqual([]);
  });

  it("pas de texte secondaire pâle (--fg-2, --fg-3, opacité sur le texte)", () => {
    const offenders = sources.filter(({ text }) => /fg-2|fg-3|text-opacity|opacity-[1-9]0|disabled:opacity/.test(text)).map((s) => s.file);
    expect(offenders).toEqual([]);
  });

  it("pas de taille de texte arbitraire (l'échelle commence à 16 px)", () => {
    const offenders = sources.filter(({ text }) => /text-\[\d|font-size:\s*\d+(\.\d+)?(px|rem|em)\b/.test(text)).map((s) => s.file);
    expect(offenders).toEqual([]);
  });

  it("interdits du contrat : ni flou d'arrière-plan, ni police distante, ni émoji", () => {
    const offenders = sources
      .filter(({ text }) => /backdrop-filter|fonts\.googleapis|fonts\.gstatic|@import\s+url\(\s*["']?https?:|[\u{1F300}-\u{1FAFF}✨]/u.test(text))
      .map((s) => s.file);
    expect(offenders).toEqual([]);
    const translated = Object.entries(fr).filter(([, v]) => /[\u{1F300}-\u{1FAFF}✨]/u.test(v)).map(([k]) => k);
    expect(translated).toEqual([]);
  });

  it("aucun texte d'interface en dur dans les composants", () => {
    const offenders: string[] = [];
    for (const { file, text } of sources.filter((s) => s.file.endsWith(".tsx"))) {
      for (const match of text.matchAll(/(?<!=)>\s*([^<>{}\n]*[A-Za-zÀ-ÿ]{2,}[^<>{}\n]*)\s*</g)) {
        const literal = match[1]?.trim() ?? "";
        if (literal && !/^[=&|?:(),.;\s\w]*=>/.test(literal) && !literal.includes("=")) offenders.push(`${file}: ${literal}`);
      }
      for (const match of text.matchAll(/(?:aria-label|alt|title|placeholder)="([^"]+)"/g)) offenders.push(`${file}: ${match[1] ?? ""}`);
    }
    expect(offenders).toEqual([]);
  });

  it("layout : data-surface=counter (zones 48 px, texte 16 px) et langue française", () => {
    const layout = sources.find((s) => s.file.endsWith("app/layout.tsx"))?.text ?? "";
    expect(layout).toContain('data-surface="counter"');
    expect(layout).toContain('lang="fr"');
  });

  it("chaque clé de traduction utilisée existe dans fr.json", () => {
    const keys = new Set(Object.keys(fr));
    const used = sources.flatMap(({ text }) => [...text.matchAll(/\bt\("([\w.-]+)"/g)].map((m) => m[1] ?? ""));
    expect(used.length).toBeGreaterThan(40);
    expect(used.filter((k) => !keys.has(k))).toEqual([]);
  });
});
