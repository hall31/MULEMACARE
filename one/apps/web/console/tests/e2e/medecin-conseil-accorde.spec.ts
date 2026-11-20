import { expect, test } from "@playwright/test";
import { t } from "../../src/i18n";
import { REVIEW_CLAIM } from "../../src/mocks/fixtures";
import { goToClaims, openAs, shot } from "./helpers";

/**
 * R5 (côté interface) — parcours « le médecin-conseil accorde un dossier en revue ».
 * Le dossier au-dessus du seuil est en revue (R-20) ; seule la décision humaine le fait passer
 * à « accordée », par POST /v1/claims/{id}/decisions avec une clé d'idempotence.
 */
test("le médecin-conseil accorde un dossier en revue", async ({ page }) => {
  await openAs(page, "medecin_conseil");
  await goToClaims(page);

  await page
    .getByRole("group", { name: t("claims.filtersLabel") })
    .getByRole("button", { name: t("claims.filterReview") })
    .click();
  await expect(page).toHaveURL(/statut=en_revue/);

  const table = page.getByRole("table", { name: t("claims.tableLabel") });
  const row = table.getByRole("row", { name: new RegExp(REVIEW_CLAIM.claim_number) });
  await expect(row).toBeVisible();
  await expect(row).toContainText(t("claimStatus.en_revue"));
  await shot(page, "01-medecin-conseil-prises-en-charge-en-revue");

  await row.click();
  const drawer = page.getByRole("dialog", {
    name: t("claim.drawerLabel", { number: REVIEW_CLAIM.claim_number }),
  });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByTestId("claim-status")).toHaveText(t("claimStatus.en_revue"));
  // La règle qui a routé le dossier est affichée avec sa version.
  await expect(drawer).toContainText(t("common.ruleWithVersion", { code: "R-20", version: 2 }));
  await shot(page, "02-medecin-conseil-tiroir-dossier-en-revue");

  await drawer.getByRole("button", { name: t("decision.approve"), exact: true }).click();

  const confirm = page.getByRole("alertdialog", {
    name: t("decision.dialogTitle.accorder", { number: REVIEW_CLAIM.claim_number }),
  });
  await expect(confirm).toBeVisible();
  await expect(confirm.getByRole("radio", { name: t("decisionReasons.ACC-01") })).toBeChecked();

  const decisionRequest = page.waitForRequest(
    (req) => req.method() === "POST" && req.url().endsWith(`/v1/claims/${REVIEW_CLAIM.id}/decisions`),
  );
  await confirm.getByRole("button", { name: t("decision.confirm.accorder") }).click();

  const request = await decisionRequest;
  expect(request.postDataJSON()).toEqual({ decision: "accorder", reason_code: "ACC-01" });
  expect(request.headers()["idempotency-key"]?.length ?? 0).toBeGreaterThanOrEqual(8);

  await expect(
    page.getByText(t("decision.success.accorder", { number: REVIEW_CLAIM.claim_number })),
  ).toBeVisible();
  await expect(drawer.getByTestId("claim-status")).toHaveText(t("claimStatus.accordee"));
  await expect(drawer.getByRole("button", { name: t("decision.approve"), exact: true })).toHaveCount(0);

  const history = drawer.getByRole("list", { name: t("claim.decisionsTitle") });
  await expect(history.getByRole("listitem").last()).toContainText(t("claim.decisionOutcome.accordee"));
  await expect(history.getByRole("listitem").last()).toContainText(t("claim.decisionSourceHuman"));
  await shot(page, "03-medecin-conseil-dossier-accorde");

  await drawer.getByRole("button", { name: t("common.close") }).click();
  await expect(drawer).toBeHidden();
  // Le dossier a quitté la file « en revue ».
  await expect(table.getByRole("row", { name: new RegExp(REVIEW_CLAIM.claim_number) })).toHaveCount(0);
});
