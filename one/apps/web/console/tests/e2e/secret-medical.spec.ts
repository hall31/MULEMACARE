import { expect, test } from "@playwright/test";
import { t } from "../../src/i18n";
import { REVIEW_CLAIM, medicalReasonFor } from "../../src/mocks/fixtures";
import { goToClaims, openAs, shot } from "./helpers";

/**
 * R6 (côté interface) — « le gestionnaire ne voit pas le motif médical ».
 * Le motif n'est jamais dans les réponses de liste ou de détail ; il n'est lu qu'à la demande,
 * par le médecin-conseil, via GET /v1/claims/{id}/medical-reason (journalisé).
 */
test("le gestionnaire ne voit pas le motif médical", async ({ page }) => {
  const medicalCalls: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes("/medical-reason")) medicalCalls.push(req.url());
  });

  await openAs(page, "gestionnaire");
  await goToClaims(page);

  const table = page.getByRole("table", { name: t("claims.tableLabel") });
  await table.getByRole("row", { name: new RegExp(REVIEW_CLAIM.claim_number) }).click();

  const drawer = page.getByRole("dialog", {
    name: t("claim.drawerLabel", { number: REVIEW_CLAIM.claim_number }),
  });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByTestId("claim-status")).toHaveText(t("claimStatus.en_revue"));

  await expect(drawer.getByText(t("medical.maskedGestionnaire"))).toBeVisible();
  await expect(drawer.getByRole("button", { name: t("medical.readButton") })).toHaveCount(0);
  // Décision réservée au médecin-conseil (QUESTIONS.md Q-L0-12).
  await expect(drawer.getByRole("button", { name: t("decision.approve"), exact: true })).toHaveCount(0);

  await expect(page.getByText(medicalReasonFor(REVIEW_CLAIM.id))).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(medicalReasonFor(REVIEW_CLAIM.id));
  expect(medicalCalls).toEqual([]);
  await shot(page, "04-gestionnaire-motif-medical-masque");
});

test("le médecin-conseil lit le motif à la demande, avec trace d'audit", async ({ page }) => {
  await openAs(page, "medecin_conseil");
  await goToClaims(page);

  await page
    .getByRole("table", { name: t("claims.tableLabel") })
    .getByRole("row", { name: new RegExp(REVIEW_CLAIM.claim_number) })
    .click();
  const drawer = page.getByRole("dialog", {
    name: t("claim.drawerLabel", { number: REVIEW_CLAIM.claim_number }),
  });

  // Rien n'est lu tant que le médecin-conseil ne le demande pas.
  await expect(drawer.getByText(medicalReasonFor(REVIEW_CLAIM.id))).toHaveCount(0);

  const read = page.waitForResponse((res) => res.url().endsWith(`/v1/claims/${REVIEW_CLAIM.id}/medical-reason`));
  await drawer.getByRole("button", { name: t("medical.readButton") }).click();
  const response = await read;
  expect(response.status()).toBe(200);
  const body = (await response.json()) as { audit_event_id: string };

  await expect(drawer.getByText(medicalReasonFor(REVIEW_CLAIM.id))).toBeVisible();
  await expect(drawer.getByTestId("medical-audit")).toContainText(body.audit_event_id);
  await shot(page, "05-medecin-conseil-motif-lu-et-journalise");
});
