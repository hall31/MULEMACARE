import { expect, type Page } from "@playwright/test";
import fr from "../src/i18n/fr.json" with { type: "json" };
import { GOOD_CODE, MEMBER_NUMBER, MockApi } from "./mock-api";

export { fr };

/** Remplace les {paramètres} d'un texte du fichier de traduction. */
export function tr(key: keyof typeof fr, params: Record<string, string | number> = {}): string {
  return fr[key].replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`));
}

/** Montant tel qu'affiché (séparateur de milliers fr-FR : espace fine insécable). */
export function xof(amount: number): string {
  return tr("money.xof", { amount: new Intl.NumberFormat("fr-FR").format(amount) });
}

export async function openCounter(page: Page, api: MockApi = new MockApi()): Promise<MockApi> {
  await api.install(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
  // Appareil enregistré et politique hors ligne reçue avant le premier patient.
  await expect.poll(() => api.registeredPublicKey).not.toBeNull();
  await expect.poll(() => api.requests.some((r) => r.path === "/v1/counter/offline-policy")).toBe(true);
  return api;
}

export async function toIdentity(page: Page, memberNumber = MEMBER_NUMBER): Promise<void> {
  await page.getByLabel(fr["card.numberLabel"]).fill(memberNumber);
  await page.getByRole("button", { name: fr["card.lookup"] }).click();
  await expect(page.getByRole("heading", { level: 1, name: fr["identity.title"] })).toBeVisible();
}

export async function toCode(page: Page): Promise<void> {
  await toIdentity(page);
  await page.getByRole("button", { name: fr["identity.yes"] }).click();
  await expect(page.getByRole("heading", { level: 1, name: fr["code.title"] })).toBeVisible();
}

export async function toActs(page: Page): Promise<void> {
  await toCode(page);
  await page.getByLabel(fr["code.label"]).fill(GOOD_CODE);
  await page.getByRole("button", { name: fr["code.validate"] }).click();
  await expect(page.getByRole("heading", { level: 1, name: fr["acts.title"] })).toBeVisible();
}

export async function selectActs(page: Page, codes: readonly string[]): Promise<void> {
  for (const code of codes) await page.locator(`input[data-act="${code}"]`).check();
}

export interface StoredRecord {
  offline_ref: string;
  status: "en_attente" | "confirmee" | "rejetee";
  reason_code: string | null;
  input: {
    offline_ref: string;
    member_number: string;
    total_xof: number;
    covered_xof: number;
    issued_at: string;
    expires_at: string;
    signed_payload: string;
    signature: string;
  };
}

/** Lit la file de synchronisation directement dans IndexedDB. */
export async function readQueue(page: Page): Promise<StoredRecord[]> {
  return page.evaluate(
    () =>
      new Promise<StoredRecord[]>((resolve, reject) => {
        const open = indexedDB.open("mulemacare-comptoir");
        open.onerror = () => reject(open.error);
        open.onsuccess = () => {
          const request = open.result.transaction("queue", "readonly").objectStore("queue").getAll();
          request.onsuccess = () => {
            resolve(request.result as StoredRecord[]);
            open.result.close();
          };
          request.onerror = () => reject(request.error);
        };
      }),
  );
}

/** Capture de tout l'écran : la fenêtre est agrandie à la hauteur du contenu pour que la barre d'actions collée en bas ne recouvre rien. */
export async function shot(page: Page, name: string): Promise<void> {
  const viewport = page.viewportSize();
  if (!viewport) throw new Error("viewport inconnu");
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.setViewportSize({ width: viewport.width, height: Math.max(height, viewport.height) });
  await page.screenshot({ path: `screenshots/${name}.png` });
  await page.setViewportSize(viewport);
}
