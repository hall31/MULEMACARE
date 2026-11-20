/**
 * AGENTS.md (Design) : les statuts utilisent les couleurs sémantiques (ok, warn, crit), jamais
 * la couleur d'accent. Même garde-fou que la console (tests/unit/design-guards.test.ts).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { STATUS_TONE_CLASSES, SYNC_TONE } from "./tones";

const here = path.dirname(fileURLToPath(import.meta.url));
const BRAND = /accent|brand|primary/;

function tsxFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) return tsxFiles(full);
    return name.endsWith(".tsx") ? [full] : [];
  });
}

describe("statuts du comptoir", () => {
  it("chaque état de synchronisation a un ton sémantique", () => {
    for (const tone of Object.values(SYNC_TONE)) expect(["ok", "warn", "crit"]).toContain(tone);
    expect(SYNC_TONE.error).toBe("crit");
  });

  it("les classes des tons n'utilisent pas les couleurs de marque", () => {
    for (const cls of Object.values(STATUS_TONE_CLASSES)) expect(cls).not.toMatch(BRAND);
  });

  it("aucun élément role=status ou role=alert ne porte l'accent", () => {
    const offenders: string[] = [];
    for (const file of tsxFiles(path.resolve(here, ".."))) {
      // Balise ouvrante complète (elle peut tenir sur plusieurs lignes).
      for (const match of readFileSync(file, "utf8").matchAll(/<[A-Za-z][^>]*\brole="(?:status|alert)"[^>]*>/g)) {
        if (BRAND.test(match[0])) offenders.push(`${path.basename(file)}: ${match[0]}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("le bandeau de synchronisation prend sa couleur du ton sémantique", () => {
    const app = readFileSync(path.join(here, "CounterApp.tsx"), "utf8");
    const banner = app.match(/<p[^>]*data-testid="sync-banner"[^>]*>/)?.[0] ?? "";
    expect(banner).toContain("STATUS_TONE_CLASSES[SYNC_TONE[runtime.syncState]]");
  });
});
