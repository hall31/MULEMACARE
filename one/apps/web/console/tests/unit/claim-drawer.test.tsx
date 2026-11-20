// @vitest-environment jsdom
/**
 * Tiroir du dossier : le motif médical n'est ni affiché ni demandé pour le gestionnaire (R6),
 * et la décision n'est proposée qu'au médecin-conseil sur un dossier en revue (R5).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { ClaimDrawer } from "../../src/features/claims/claim-drawer";
import { t } from "../../src/i18n";
import { API_BASE_URL } from "../../src/lib/config";
import { SessionContext, demoToken, type DemoRole } from "../../src/lib/session";
import { AUTO_CLAIM, REVIEW_CLAIM, medicalReasonFor } from "../../src/mocks/fixtures";
import { server } from "../../src/mocks/node";

function renderDrawer(role: DemoRole, claimId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const session = {
    mode: "demo" as const,
    role,
    token: demoToken(role),
    setRole: () => undefined,
  };
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </SessionContext.Provider>
  );
  return { client, ...render(<ClaimDrawer claimId={claimId} onClose={() => undefined} />, { wrapper }) };
}

/** Tout ce que le cache de mutations retient encore (données, variables, contexte). */
function mutationCacheDump(client: QueryClient): string {
  return JSON.stringify(client.getMutationCache().getAll().map((m) => m.state));
}

function trackMedicalReads(): string[] {
  const calls: string[] = [];
  server.events.on("request:start", ({ request }) => {
    if (request.url.includes("/medical-reason")) calls.push(request.url);
  });
  return calls;
}

describe("ClaimDrawer", () => {
  it("gestionnaire : motif masqué, aucun bouton, aucune requête vers le motif", async () => {
    const calls = trackMedicalReads();
    renderDrawer("gestionnaire", REVIEW_CLAIM.id);
    const dialog = await screen.findByRole("dialog", { name: t("claim.drawerLabel", { number: REVIEW_CLAIM.claim_number }) });
    await within(dialog).findByText(t("claimStatus.en_revue"));
    expect(within(dialog).getByText(t("medical.maskedGestionnaire"))).toBeTruthy();
    expect(within(dialog).queryByRole("button", { name: t("medical.readButton") })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: t("decision.approve") })).toBeNull();
    expect(document.body.textContent).not.toContain(medicalReasonFor(REVIEW_CLAIM.id));
    expect(calls).toEqual([]);
  });

  it("médecin-conseil : le motif n'est lu qu'au clic, avec sa trace d'audit", async () => {
    const calls = trackMedicalReads();
    const user = userEvent.setup();
    renderDrawer("medecin_conseil", REVIEW_CLAIM.id);
    const dialog = await screen.findByRole("dialog");
    const button = await within(dialog).findByRole("button", { name: t("medical.readButton") });
    expect(calls).toEqual([]);
    await user.click(button);
    expect(await within(dialog).findByText(medicalReasonFor(REVIEW_CLAIM.id))).toBeTruthy();
    expect(within(dialog).getByTestId("medical-audit").textContent).toMatch(/[0-9a-f-]{36}/);
    expect(calls).toHaveLength(1);
  });

  it("médecin-conseil : le motif ne reste pas en mémoire après fermeture du tiroir", async () => {
    const user = userEvent.setup();
    const { client, unmount } = renderDrawer("medecin_conseil", REVIEW_CLAIM.id);
    const dialog = await screen.findByRole("dialog");
    await user.click(await within(dialog).findByRole("button", { name: t("medical.readButton") }));
    await within(dialog).findByText(medicalReasonFor(REVIEW_CLAIM.id));
    unmount();
    await waitFor(() => expect(mutationCacheDump(client)).not.toContain(medicalReasonFor(REVIEW_CLAIM.id)));
    expect(client.getMutationCache().getAll()).toHaveLength(0);
  });

  it("médecin-conseil : « Masquer » efface aussi le motif du cache", async () => {
    const user = userEvent.setup();
    const { client } = renderDrawer("medecin_conseil", REVIEW_CLAIM.id);
    const dialog = await screen.findByRole("dialog");
    await user.click(await within(dialog).findByRole("button", { name: t("medical.readButton") }));
    await within(dialog).findByText(medicalReasonFor(REVIEW_CLAIM.id));
    await user.click(within(dialog).getByRole("button", { name: t("medical.hide") }));
    expect(within(dialog).queryByText(medicalReasonFor(REVIEW_CLAIM.id))).toBeNull();
    await waitFor(() => expect(mutationCacheDump(client)).not.toContain(medicalReasonFor(REVIEW_CLAIM.id)));
  });

  it("médecin-conseil : pas de décision sur un dossier accordé automatiquement", async () => {
    renderDrawer("medecin_conseil", AUTO_CLAIM.id);
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText(t("claimStatus.accordee_auto"));
    expect(within(dialog).queryByRole("button", { name: t("decision.approve") })).toBeNull();
  });

  it("erreur HealthOS : message du contrat et action proposée", async () => {
    server.use(
      http.get(`${API_BASE_URL}/v1/claims/:id/medical-reason`, () =>
        HttpResponse.json(
          {
            code: "INT-01",
            message: "Le dossier médical est momentanément indisponible.",
            action: "Réessayez dans quelques minutes.",
            request_id: "req_test",
          },
          { status: 502, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderDrawer("medecin_conseil", REVIEW_CLAIM.id);
    const dialog = await screen.findByRole("dialog");
    await user.click(await within(dialog).findByRole("button", { name: t("medical.readButton") }));
    await waitFor(() => expect(within(dialog).getByText("Le dossier médical est momentanément indisponible.")).toBeTruthy());
    expect(within(dialog).getByText("Réessayez dans quelques minutes.")).toBeTruthy();
  });
});
