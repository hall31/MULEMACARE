/** Les types du client sont générés depuis le contrat ; ce test échoue s'ils ont dérivé. */
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
import { expect, it } from "vitest";

const here = path.dirname(fileURLToPath(import.meta.url));

it("src/api/schema.d.ts correspond à specs/openapi.yaml (pnpm gen:api)", async () => {
  const spec = pathToFileURL(path.resolve(here, "../../../../../specs/openapi.yaml"));
  const generated = astToString(await openapiTS(spec));
  const committed = readFileSync(path.resolve(here, "../../src/api/schema.d.ts"), "utf8");
  const body = (s: string) => s.slice(s.indexOf("export interface paths"));
  expect(body(committed).trim()).toBe(body(generated).trim());
}, 20_000);
