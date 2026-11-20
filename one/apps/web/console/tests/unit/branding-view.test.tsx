// @vitest-environment jsdom
/**
 * Écran « Marque de l'organisation » (P3) : aperçu et contraste en direct, refus de l'API (BRD-01)
 * affiché clairement sous le champ avec la couleur conforme la plus proche, enregistrement,
 * états chargement / erreur, réservé à l'administrateur.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { BrandingView } from "../../src/features/branding/branding-view";
import { t } from "../../src/i18n";
import { API_BASE_URL } from "../../src/lib/config";
import { SessionContext, demoToken, type DemoRole } from "../../src/lib/session";
import { server } from "../../src/mocks/node";
import { demoState } from "../../src/mocks/store";

function renderView(role: DemoRole = "admin") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const session = { mode: "demo" as const, role, token: demoToken(role), setRole: () => undefined };
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </SessionContext.Provider>
  );
  return render(<BrandingView />, { wrapper });
}

const accentLabel = t("branding.token.accent");

describe("marque de l'organisation", () => {
  it("couleur illisible : contraste dit en direct, refus BRD-01 sous le champ, couleur conforme proposée puis enregistrée", async () => {
    const user = userEvent.setup();
    renderView();
    const light = await screen.findByTestId("colors-light");
    const accent = within(light).getByLabelText(accentLabel);
    expect(within(light).getByTestId("contrast-light").textContent).toContain(t("branding.contrastOk"));

    await user.clear(accent);
    await user.type(accent, "#ffd400");
    expect(within(light).getByTestId("contrast-light").textContent).not.toContain(t("branding.contrastOk"));
    expect(accent.getAttribute("aria-invalid")).toBe("true");
    expect(within(light).getByTestId("light-accent-erreur").textContent).toContain(t("branding.liveContrast"));
    // L'aperçu suit la saisie (variables posées sur le cadre).
    expect(screen.getByTestId("brand-preview-light").style.getPropertyValue("--accent")).toBe("#ffd400");

    await user.click(screen.getByRole("button", { name: t("branding.submit") }));
    const alert = await screen.findByTestId("branding-api-error");
    expect(alert.getAttribute("data-code")).toBe("BRD-01");
    expect(alert.textContent).toContain(t("branding.contrastRefused"));
    expect(alert.textContent).toContain(t("branding.code", { code: "BRD-01" }));
    expect(within(light).getByTestId("light-accent-erreur").textContent).toMatch(/--accent sur --surface donne 1,43:1/);
    expect(accent.getAttribute("aria-describedby")).toContain("light-accent-erreur");

    const suggest = within(light).getByTestId("suggest-light-accent");
    await user.click(suggest);
    const fixed = (accent as HTMLInputElement).value;
    expect(fixed).toMatch(/^#[0-9a-f]{6}$/);
    expect(fixed).not.toBe("#ffd400");
    expect(within(light).getByTestId("contrast-light").textContent).toContain(t("branding.contrastOk"));

    await user.click(screen.getByRole("button", { name: t("branding.submit") }));
    expect((await screen.findByTestId("branding-saved")).textContent).toContain(t("branding.savedTitle"));
    expect(demoState().branding.theme.light?.accent).toBe(fixed);
  }, 20_000);

  it("format invalide : rien n'est envoyé, le champ dit le format attendu", async () => {
    const user = userEvent.setup();
    let calls = 0;
    server.events.on("request:start", ({ request }) => {
      if (request.method === "PUT") calls += 1;
    });
    renderView();
    const dark = await screen.findByTestId("colors-dark");
    await user.type(within(dark).getByLabelText(accentLabel), "vert");
    await user.click(screen.getByRole("button", { name: t("branding.submit") }));
    expect(document.activeElement).toBe(await screen.findByTestId("branding-local-errors"));
    expect(within(dark).getByTestId("dark-accent-erreur").textContent).toContain(t("branding.errors.format"));
    expect(calls).toBe(0);
  }, 20_000);

  it("domaine déjà déclaré (BRD-04) : message sous le domaine", async () => {
    const user = userEvent.setup();
    renderView();
    const domain = await screen.findByLabelText(t("branding.customDomain"));
    await user.type(domain, "sante.deja-pris.ci");
    await user.click(screen.getByRole("button", { name: t("branding.submit") }));
    expect((await screen.findByTestId("branding-api-error")).getAttribute("data-code")).toBe("BRD-04");
    expect(screen.getByTestId("custom_domain-erreur")).toBeTruthy();
  }, 20_000);

  it("domaine : enregistrement TXT à publier, vérification refusée (BRD-06) puis réussie", async () => {
    const user = userEvent.setup();
    renderView();
    const domain = await screen.findByLabelText(t("branding.customDomain"));
    await user.type(domain, "attente.lagune-sante.ci");
    await user.click(screen.getByRole("button", { name: t("branding.submit") }));
    const proof = await screen.findByTestId("domain-proof");
    expect(proof.getAttribute("data-status")).toBe("en_attente_de_verification");
    expect(screen.getByTestId("dns-record-name").textContent).toBe("_mulemacare-verification.attente.lagune-sante.ci");
    await user.click(screen.getByRole("button", { name: t("branding.domainVerify") }));
    const refused = await screen.findByTestId("domain-error");
    expect(refused.getAttribute("data-code")).toBe("BRD-06");
    expect(refused.textContent).toContain(t("branding.errorTitles.BRD-06"));

    await user.clear(domain);
    await user.type(domain, "sante.lagune-sante.ci");
    expect(screen.getByTestId("domain-unsaved")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: t("branding.submit") }));
    await screen.findByTestId("domain-proof");
    await user.click(screen.getByRole("button", { name: t("branding.domainVerify") }));
    expect((await screen.findByTestId("domain-verified")).textContent).toContain(t("branding.domainVerifiedNow"));
    expect(screen.getByTestId("domain-proof").getAttribute("data-status")).toBe("verifie");
  }, 20_000);

  it("domaine réservé (BRD-05) : titre clair et message sous le domaine", async () => {
    const user = userEvent.setup();
    renderView();
    await user.type(await screen.findByLabelText(t("branding.customDomain")), "payer.mulemacare.invalid");
    await user.click(screen.getByRole("button", { name: t("branding.submit") }));
    const alert = await screen.findByTestId("branding-api-error");
    expect(alert.getAttribute("data-code")).toBe("BRD-05");
    expect(alert.textContent).toContain(t("branding.errorTitles.BRD-05"));
    expect(screen.getByTestId("custom_domain-erreur")).toBeTruthy();
  }, 20_000);

  it("erreur de lecture : code, message et Réessayer", async () => {
    server.use(
      http.get(`${API_BASE_URL}/v1/organization/branding`, () =>
        HttpResponse.json({ code: "SYS-01", message: "Le service est indisponible.", action: "Réessayez dans un instant.", request_id: "req_1" }, { status: 503, headers: { "Content-Type": "application/problem+json" } }),
      ),
    );
    renderView();
    expect((await screen.findByRole("alert")).textContent).toContain("Le service est indisponible.");
    expect(screen.getByRole("button", { name: t("states.retry") })).toBeTruthy();
  }, 20_000);

  it("réservé à l'administrateur de l'organisation", async () => {
    renderView("gestionnaire");
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain(t("forbidden.adminOnly")));
  }, 20_000);
});
