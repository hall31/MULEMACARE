import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Dérive des types générés : `src/api/schema.d.ts` doit être exactement ce que produit
 * `openapi-typescript` aujourd'hui depuis `specs/openapi.yaml` (même binaire, mêmes options que
 * `make gen-api`). Un contrat modifié sans régénération fait échouer `make test`. Environ 2 s.
 */
const app = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const SPEC = path.join(app, "../../../specs/openapi.yaml");
const COMMITTED = path.join(app, "src/api/schema.d.ts");
const BIN = path.join(app, "node_modules/.bin/openapi-typescript");

describe("types générés depuis le contrat", () => {
  it("schema.d.ts est identique à une génération fraîche (sinon : make gen-api)", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "schema-drift-"));
    try {
      const fresh = path.join(dir, "schema.d.ts");
      execFileSync(BIN, [SPEC, "-o", fresh], { cwd: app, stdio: "pipe", timeout: 60_000 });
      const committed = readFileSync(COMMITTED, "utf8");
      const generated = readFileSync(fresh, "utf8");
      expect(committed === generated, "src/api/schema.d.ts a dérivé de specs/openapi.yaml : lancer `make gen-api`").toBe(true);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }, 60_000);
});
