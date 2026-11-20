// @vitest-environment jsdom
/**
 * Espaces assureur et employeur : états obligatoires (chargement, erreur avec code et Réessayer,
 * vide, masqué), effectifs par tranche jamais exacts, valeurs écrites en texte à côté des barres,
 * tableau alternatif, export CSV, période publiée, garde de rôle.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { EmployerView } from "../../src/features/employer/employer-view";
import { PortfolioView } from "../../src/features/insurer/portfolio-view";
import { t } from "../../src/i18n";
import { API_BASE_URL } from "../../src/lib/config";
import { SessionContext, demoToken, type DemoRole } from "../../src/lib/session";
import { addDays, employerConsumption, insurerPortfolio, today } from "../../src/mocks/data";
import { server } from "../../src/mocks/node";

vi.mock("next/navigation", () => ({ usePathname: () => "/", useRouter: () => ({ replace: () => undefined }) }));

function renderWith(node: ReactNode, role: DemoRole) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const session = { mode: "demo" as const, role, token: demoToken(role), setRole: () => undefined };
  return render(
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={client}>{node}</QueryClientProvider>
    </SessionContext.Provider>,
  );
}

const problem = (status: number, code: string) =>
  HttpResponse.json({ code, message: "Le service est indisponible.", action: "Réessayez dans un instant.", request_id: "req_test" }, { status, headers: { "Content-Type": "application/problem+json" } });

describe("espace assureur", () => {
  it("portefeuille : indicateurs, tranches d'effectif, statuts masqués ensemble, période publiée", async () => {
    renderWith(<PortfolioView />, "assureur");
    const members = await screen.findByTestId("kpi-members");
    expect(members.textContent).toContain(t("kanon.countOpen", { from: 100 }));
    expect(members.textContent).toContain(t("kanon.carriedBy", { tier: t("kanon.tierOpen", { from: 100 }) }));
    expect(members.textContent).not.toMatch(/439/);
    const statuses = within(screen.getByTestId("chart-statuts")).getAllByTestId("bar-row");
    expect(statuses.map((r) => [r.getAttribute("data-key"), r.getAttribute("data-status")])).toEqual([["actif", "disponible"], ["carence", "masque"], ["suspendu", "masque"]]);
    expect(statuses[1]!.textContent).toContain(t("kanon.masked"));
    expect(screen.getByTestId("masked-note").textContent).toContain(t("kanon.noteTitle", { k: 5 }));
    expect(screen.getByTestId("published-period").textContent).toMatch(/Période publiée : du \d{2}\/\d{2}\/\d{4} au/);
    // Chaque barre a sa valeur écrite et un tableau alternatif.
    const categories = screen.getByTestId("chart-categories");
    expect(within(categories).getAllByRole("table")).toHaveLength(1);
    expect(within(categories).getAllByTestId("bar-row")[0]!.textContent).toMatch(/≈ .*FCFA/);
    expect(screen.getAllByTestId("provider-row").length).toBeLessThanOrEqual(5);
  }, 20_000);

  it("chargement puis erreur : code stable, message, Réessayer qui relance", async () => {
    let calls = 0;
    server.use(
      http.get(`${API_BASE_URL}/v1/insurer/portfolio`, async () => {
        calls += 1;
        await delay(50);
        return calls === 1 ? problem(503, "SYS-01") : HttpResponse.json(insurerPortfolio(addDays(today(), -29), today()));
      }),
    );
    const user = userEvent.setup();
    renderWith(<PortfolioView />, "assureur");
    expect(await screen.findByTestId("loading")).toBeTruthy();
    const error = await screen.findByTestId("error-state");
    expect(error.textContent).toContain("Le service est indisponible.");
    expect(error.textContent).toContain(t("states.code", { code: "SYS-01" }));
    await user.click(within(error).getByRole("button", { name: t("states.retry") }));
    expect(await screen.findByTestId("portfolio")).toBeTruthy();
  }, 20_000);

  it("période sans soin : état vide (aucune catégorie, aucun prestataire)", async () => {
    const empty = { ...insurerPortfolio(addDays(today(), -29), today()), benefits_by_category: [], top_providers: [], claims_cost_xof: { status: "masque" as const, value: null, contributors: null } };
    server.use(http.get(`${API_BASE_URL}/v1/insurer/portfolio`, () => HttpResponse.json(empty)));
    renderWith(<PortfolioView />, "assureur");
    const states = await screen.findAllByTestId("empty-state");
    expect(states.map((s) => s.textContent).join(" ")).toContain(t("insurer.noCareTitle"));
  }, 20_000);

  it("export CSV agrégé : fichier proposé au téléchargement, mêmes masques", async () => {
    const created: Blob[] = [];
    URL.createObjectURL = vi.fn((blob: Blob) => {
      created.push(blob);
      return "blob:portefeuille";
    });
    URL.revokeObjectURL = vi.fn();
    HTMLAnchorElement.prototype.click = vi.fn();
    const user = userEvent.setup();
    renderWith(<PortfolioView />, "assureur");
    await screen.findByTestId("portfolio");
    await user.click(screen.getByTestId("export-csv"));
    const link = await screen.findByTestId("export-link");
    expect(link.getAttribute("download")).toMatch(/^portefeuille-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}\.csv$/);
    // Blob de jsdom sans .text() : lu par FileReader.
    const csv = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(created[0]!);
    });
    expect(csv.split("\r\n")[0]).toBe("section;cle;statut;valeur;effectif;unite");
    expect(csv).toContain("adherents;suspendu;masque;;;nombre");
  }, 20_000);

  it("réservé à l'assureur (et à l'admin)", async () => {
    renderWith(<PortfolioView />, "employeur");
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain(t("states.forbiddenTitle")));
  });
});

describe("espace employeur", () => {
  it("consommation par groupe ; petit groupe masqué ; contrats à échéance triés, statut en mot", async () => {
    renderWith(<EmployerView />, "employeur");
    const groups = await screen.findAllByTestId("employer-group");
    expect(groups).toHaveLength(2);
    expect(groups[1]!.textContent).toContain(t("employer.smallGroup", { k: 5 }));
    const rows = await screen.findAllByTestId("contract-row");
    expect(rows.map((r) => r.getAttribute("data-status"))).toEqual(["echu", "a_echeance", "en_cours", "sans_echeance"]);
    expect(rows[1]!.textContent).toContain(t("contractStatus.a_echeance"));
    expect(screen.getByTestId("contracts-summary").textContent).toBe(t("employer.contractsSummary", { count: 1, days: 90 }));
    // Aucun nom de salarié : seuls les noms d'employeurs fictifs apparaissent.
    expect(document.body.textContent).not.toMatch(/Nadia|Ouattara/);
  }, 20_000);

  it("horizon d'échéance élargi à 365 jours : le contrat à 200 jours devient « échéance proche »", async () => {
    const user = userEvent.setup();
    renderWith(<EmployerView />, "employeur");
    await screen.findAllByTestId("contract-row");
    await user.selectOptions(screen.getByLabelText(t("employer.horizon")), "365");
    await waitFor(() => expect(screen.getByTestId("contracts-summary").textContent).toBe(t("employer.contractsSummary", { count: 2, days: 365 })));
  }, 20_000);

  it("aucun groupe rattaché : état vide qui dit pourquoi", async () => {
    server.use(http.get(`${API_BASE_URL}/v1/employer/consumption`, () => HttpResponse.json({ ...employerConsumption(addDays(today(), -29), today()), groups: [] })));
    renderWith(<EmployerView />, "employeur");
    const empty = await screen.findAllByTestId("empty-state");
    expect(empty.map((e) => e.textContent).join(" ")).toContain(t("employer.noGroupTitle"));
  }, 20_000);

  it("période sans semaine terminée : 422 VAL-01 expliqué", async () => {
    server.use(http.get(`${API_BASE_URL}/v1/employer/consumption`, () => problem(422, "VAL-01")));
    renderWith(<EmployerView />, "employeur");
    expect((await screen.findByTestId("error-state")).textContent).toContain(t("states.code", { code: "VAL-01" }));
  }, 20_000);
});
