import { expect, test } from "@playwright/test";
import { verifySignature, fromBase64url } from "../src/offline/signing";
import { fr, openCounter, readQueue, selectActs, shot, toActs, tr, xof } from "./flow";

test.describe("R13 — hors ligne", () => {
  test("réseau coupé : un dossier sous le seuil est accordé en provisoire, signé sur l'appareil, puis synchronisé", async ({ page, context }) => {
    const api = await openCounter(page);
    await toActs(page);

    // Coupure réseau au comptoir.
    api.networkDown = true;
    await context.setOffline(true);
    await expect(page.getByTestId("offline-banner-title")).toHaveText(tr("net.offline.withPolicy", { threshold: xof(50_000) }));

    await selectActs(page, ["CS-GEN", "NFS", "ECG"]);
    await page.getByRole("button", { name: fr["acts.submit"] }).click();

    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.provisional"] })).toBeVisible();
    await expect(page.getByTestId("collect")).toContainText(xof(9_600));
    await expect(page.getByText(xof(38_400))).toBeVisible();
    expect(api.claimRequests(), "aucune demande n'a pu partir").toHaveLength(0);

    // Accord signé et mis en file dans IndexedDB, valable 2 h.
    const [record, ...others] = await readQueue(page);
    expect(others).toHaveLength(0);
    expect(record).toBeDefined();
    if (!record) return;
    expect(record.status).toBe("en_attente");
    expect(record.input).toMatchObject({ member_number: "MC-00000042", total_xof: 48_000, covered_xof: 38_400 });
    expect(Date.parse(record.input.expires_at) - Date.parse(record.input.issued_at)).toBe(2 * 3_600_000);
    expect(api.registeredPublicKey).not.toBeNull();
    expect(await verifySignature(api.registeredPublicKey ?? "", record.input.signed_payload, record.input.signature), "signature vérifiable avec la clé enregistrée").toBe(true);
    const signed = JSON.parse(new TextDecoder().decode(fromBase64url(record.input.signed_payload))) as Record<string, unknown>;
    expect(signed).toMatchObject({ offline_ref: record.offline_ref, total_xof: 48_000, covered_xof: 38_400, expires_at: record.input.expires_at });
    await expect(page.getByTestId("sync-banner")).toHaveText(tr("sync.pending.one"));
    await expect(page.getByTestId("provisional-status")).toContainText("Signé sur cet appareil");
    await shot(page, "06-hors-ligne-accord-provisoire");

    // Retour du réseau : rapprochement automatique.
    api.networkDown = false;
    await context.setOffline(false);
    await expect(page.getByTestId("provisional-status")).toHaveText(fr["decision.provisionalSynced"]);
    await expect(page.getByTestId("sync-banner")).toHaveCount(0);
    expect(api.syncBodies).toHaveLength(1);
    const sent = api.syncBodies[0];
    expect(sent?.device_id).toBe("7d4c2b1a-0f9e-4d8c-b7a6-5e4d3c2b1a09");
    expect(sent?.authorizations).toEqual([expect.objectContaining({ offline_ref: record.offline_ref, signature: record.input.signature, signed_payload: record.input.signed_payload })]);
    expect((await readQueue(page)).map((r) => r.status)).toEqual(["confirmee"]);
    await shot(page, "07-hors-ligne-synchronise");

    // Patient suivant : l'accord confirmé quitte l'appareil.
    await page.getByRole("button", { name: fr["decision.next"] }).click();
    await expect.poll(() => readQueue(page)).toEqual([]);
  });

  test("réseau coupé : au-dessus du seuil, aucun accord provisoire n'est signé", async ({ page, context }) => {
    const api = await openCounter(page);
    await toActs(page);
    api.networkDown = true;
    await context.setOffline(true);

    await selectActs(page, ["CS-GEN", "NFS", "ECG", "ECHO-ABD"]);
    await page.getByRole("button", { name: fr["acts.submit"] }).click();

    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.offlineBlocked"] })).toBeVisible();
    await expect(page.getByRole("alert").filter({ hasText: tr("decision.offline.aboveThreshold", { threshold: xof(50_000) }) })).toBeVisible();
    expect(await readQueue(page)).toEqual([]);

    // Au retour du réseau, la même demande part au moteur de règles (même clé d'idempotence).
    api.networkDown = false;
    await context.setOffline(false);
    await page.getByRole("button", { name: fr["decision.retry"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.review"] })).toBeVisible();
    expect(api.claimRequests()).toHaveLength(1);
  });

  test("un refus de la mutuelle à la synchronisation est signalé avec son code", async ({ page, context }) => {
    const api = await openCounter(page);
    api.syncOutcome = "rejetee";
    await toActs(page);
    api.networkDown = true;
    await context.setOffline(true);
    await selectActs(page, ["NFS"]);
    await page.getByRole("button", { name: fr["acts.submit"] }).click();
    await expect(page.getByRole("heading", { level: 1, name: fr["decision.title.provisional"] })).toBeVisible();
    api.networkDown = false;
    await context.setOffline(false);
    await expect(page.getByTestId("provisional-status")).toHaveText(tr("decision.provisionalRejected", { code: "OFF-01" }));
    expect((await readQueue(page)).map((r) => [r.status, r.reason_code])).toEqual([["rejetee", "OFF-01"]]);
  });
});
