import { expect, test } from "@playwright/test";
import { fr, openCounter, selectActs, shot, toActs, toCode, toIdentity, tr, xof } from "./flow";

test.describe("R1 — comptoir en ligne, cinq écrans", () => {
  test("carte, identité, code, actes, décision : 48 000 FCFA accordés automatiquement", async ({ page }) => {
    const api = await openCounter(page);
    // Nouvelle direction : « 1 sur 5 · Carte » (numéro d'étape en Outfit) remplace « ÉTAPE 1 SUR 5 ».
    await expect(page.getByTestId("step")).toHaveText(`1 ${tr("step.of", { name: fr["step.name.card"] })}`);
    await shot(page, "01-carte");

    await toIdentity(page);
    await expect(page.getByText("Aya Démo")).toBeVisible();
    await expect(page.getByText(fr["identity.status.actif"])).toBeVisible();
    await shot(page, "02-identite");

    await page.getByRole("button", { name: fr["identity.yes"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["code.title"] })).toBeVisible();
    await expect(page.getByLabel(fr["code.label"])).toHaveAttribute("inputmode", "numeric");
    await expect(page.getByLabel(fr["code.label"])).toHaveAttribute("autocomplete", "one-time-code");
    await shot(page, "03-code");

    await page.getByLabel(fr["code.label"]).fill("482913");
    await page.getByRole("button", { name: fr["code.validate"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["acts.title"] })).toBeVisible();
    await selectActs(page, ["CS-GEN", "NFS", "ECG"]);
    await expect(page.getByText(xof(48_000))).toBeVisible();
    await shot(page, "04-actes");

    await page.getByRole("button", { name: fr["acts.submit"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.auto"] })).toBeVisible();
    await expect(page.getByTestId("collect")).toContainText(xof(9_600));
    await expect(page.getByText(tr("decision.rule", { code: "R-12", version: 3 }))).toBeVisible();
    await shot(page, "05-decision");

    const [claim] = api.claimRequests();
    expect(claim?.body).toEqual({ identification_id: "0b8f3f5e-4d1c-4a55-9d5a-2f7c1c3e9a01", service_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/), items: [{ act_code: "CS-GEN", quantity: 1 }, { act_code: "NFS", quantity: 1 }, { act_code: "ECG", quantity: 1 }] });
    expect(claim?.headers["idempotency-key"]).toMatch(/^[0-9a-f-]{36}$/);

    await page.getByRole("button", { name: fr["decision.next"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
  });

  test("au-dessus du seuil, le dossier part au médecin-conseil", async ({ page }) => {
    await openCounter(page);
    await toActs(page);
    await selectActs(page, ["CS-GEN", "ECHO-ABD"]);
    await page.getByRole("button", { name: fr["acts.submit"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.review"] })).toBeVisible();
    await expect(page.getByTestId("collect")).toHaveCount(0);
  });

  test("trois codes faux bloquent la carte (ID-04) et ramènent à la carte", async ({ page }) => {
    await openCounter(page);
    await toCode(page);
    const input = page.getByLabel(fr["code.label"]);
    for (const [attempt, left] of [[1, 2], [2, 1]] as const) {
      await input.fill("000000");
      await page.getByRole("button", { name: fr["code.validate"] }).click();
      await expect(page.getByTestId("flash"), `essai ${attempt}`).toContainText(`Il reste ${left} essai`);
    }
    await input.fill("000000");
    await page.getByRole("button", { name: fr["code.validate"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
    await expect(page.getByTestId("flash")).toContainText("Carte bloquée pendant 15 minutes");
    await expect(page.getByTestId("flash")).toContainText("Carte bloquée jusqu'à");
  });

  test("identité refusée : retour à la carte avec signalement", async ({ page }) => {
    const api = await openCounter(page);
    await toIdentity(page);
    await page.getByRole("button", { name: fr["identity.no"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["card.title"] })).toBeVisible();
    await expect(page.getByTestId("flash")).toHaveText(fr["identity.refused"]);
    expect(api.requests.find((r) => r.path.endsWith("/photo-confirmation"))?.body).toEqual({ confirmed: false });
  });

  test("numéro mal formé ou carte inconnue : message qui dit quoi faire", async ({ page }) => {
    await openCounter(page);
    await page.getByLabel(fr["card.numberLabel"]).fill("12345");
    await page.getByRole("button", { name: fr["card.lookup"] }).click();
    await expect(page.getByText(fr["card.numberInvalid"])).toBeVisible();
    await page.getByLabel(fr["card.numberLabel"]).fill("MC-99999999");
    await page.getByRole("button", { name: fr["card.lookup"] }).click();
    await expect(page.getByTestId("flash")).toContainText("Aucune carte active ne correspond");
  });

  test("mode plein soleil : noir sur blanc, mémorisé sur l'appareil", async ({ page }) => {
    await openCounter(page);
    const toggle = page.getByRole("button", { name: fr["bar.sun.label"] });
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("html")).toHaveAttribute("data-sun", "");
    const colors = await page.evaluate(() => {
      const style = getComputedStyle(document.querySelector(".min-h-dvh") as Element);
      return { fg: getComputedStyle(document.querySelector("h1") as Element).color, bg: style.backgroundColor };
    });
    expect(colors).toEqual({ fg: "rgb(0, 0, 0)", bg: "rgb(255, 255, 255)" });
    await toActs(page);
    await selectActs(page, ["CS-GEN", "NFS"]);
    await shot(page, "08-plein-soleil-actes");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-sun", "");
  });
});
