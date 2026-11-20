// @vitest-environment jsdom
/**
 * Écran « Organisations » (P3) : formulaire accessible validé avant envoi, ORG-01 et ORG-02 sous
 * leur champ, preuve de l'accueil, gabarits publiés, réservé à l'administrateur de plateforme.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { OrganizationsView } from "../../src/features/platform/organizations-view";
import { t } from "../../src/i18n";
import { API_BASE_URL } from "../../src/lib/config";
import { SessionContext, demoToken, type DemoRole } from "../../src/lib/session";
import { server } from "../../src/mocks/node";

function renderView(role: DemoRole = "admin_plateforme") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const session = { mode: "demo" as const, role, token: demoToken(role), setRole: () => undefined };
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </SessionContext.Provider>
  );
  return render(<OrganizationsView />, { wrapper });
}

async function fill(user: ReturnType<typeof userEvent.setup>, slug: string) {
  await user.type(await screen.findByLabelText(t("organizations.name")), "Mutuelle de Bouaké");
  await user.type(screen.getByLabelText(t("organizations.slug")), slug);
  await user.type(screen.getByLabelText(t("organizations.managerName")), "Adjoua Kouamé");
  await user.type(screen.getByLabelText(t("organizations.managerSubject")), "idp|bouake-001");
  await screen.findAllByTestId("template-row");
}

describe("accueil d'organisation", () => {
  it("envoi vide : résumé d'erreurs focalisé, chaque champ dit quoi corriger (aria-describedby)", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findAllByTestId("template-row");
    await user.click(screen.getByRole("button", { name: t("organizations.submit") }));
    expect(document.activeElement).toBe(await screen.findByTestId("organization-error"));
    const slug = screen.getByLabelText(t("organizations.slug"));
    expect(slug.getAttribute("aria-invalid")).toBe("true");
    expect(slug.getAttribute("aria-describedby")).toContain("org-slug-erreur");
    expect(screen.getByTestId("org-slug-erreur").textContent).toContain(t("organizations.errors.slug"));
    expect(screen.getByTestId("org-name-erreur").textContent).toContain(t("organizations.errors.required"));
  }, 20_000);

  it("identifiant déjà pris : ORG-01 sous l'identifiant", async () => {
    const user = userEvent.setup();
    renderView();
    await fill(user, "lagune-sante");
    await user.click(screen.getByRole("button", { name: t("organizations.submit") }));
    expect((await screen.findByTestId("organization-error")).getAttribute("data-code")).toBe("ORG-01");
    expect(screen.getByTestId("org-slug-erreur").textContent).toContain("Cet identifiant public d'organisation est déjà utilisé.");
  }, 20_000);

  it("gabarit refusé par l'API : ORG-02 sous le gabarit", async () => {
    server.use(
      http.post(`${API_BASE_URL}/v1/platform/organizations`, () =>
        HttpResponse.json({ code: "ORG-02", message: "Ce gabarit de configuration est introuvable ou prévu pour un autre pays.", action: "Choisissez un gabarit du même pays.", request_id: "r" }, { status: 422, headers: { "Content-Type": "application/problem+json" } }),
      ),
    );
    const user = userEvent.setup();
    renderView();
    await fill(user, "mutuelle-bouake");
    await user.click(screen.getByRole("button", { name: t("organizations.submit") }));
    expect((await screen.findByTestId("organization-error")).getAttribute("data-code")).toBe("ORG-02");
    expect(screen.getByTestId("org-template-erreur").textContent).toContain("autre pays");
  }, 20_000);

  it("pays changé : seuls ses gabarits sont proposés ; accueil réussi avec sa preuve, ajouté à la liste", async () => {
    const user = userEvent.setup();
    renderView();
    await fill(user, "mutuelle-thies");
    await user.click(screen.getByRole("radio", { name: t("countries.SN") }));
    const template = screen.getByLabelText(t("organizations.template"));
    expect(within(template).getAllByRole("option").map((o) => o.getAttribute("value"))).toEqual(["mutuelle-sn@1"]);
    await user.click(screen.getByRole("button", { name: t("organizations.submit") }));
    const proof = await screen.findByTestId("organization-created");
    expect(proof.textContent).toContain(t("organizations.createdProof", { slug: "mutuelle-thies", code: "mutuelle-sn", version: 1 }));
    expect(proof.textContent).toMatch(/Gestionnaire mutuelle, Administrateur/);
    expect(screen.getAllByTestId("onboarded-row")).toHaveLength(1);
  }, 20_000);

  it("publier une version de gabarit", async () => {
    const user = userEvent.setup();
    renderView();
    await screen.findAllByTestId("template-row");
    await user.type(screen.getByLabelText(t("organizations.templateCode")), "mutuelle-ci");
    await user.type(screen.getByLabelText(t("organizations.templateLabel")), "Référence CI");
    await user.click(screen.getByRole("button", { name: t("organizations.publish") }));
    expect((await screen.findByTestId("template-published")).textContent).toContain(t("organizations.published", { code: "mutuelle-ci", version: 3 }));
  }, 20_000);

  it("réservé à l'administrateur de plateforme", async () => {
    renderView("admin");
    expect((await screen.findByRole("alert")).textContent).toContain(t("forbidden.platformOnly"));
  }, 20_000);
});
