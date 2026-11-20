// @vitest-environment jsdom
/**
 * Page « Mesure » : indicateurs de getProductMetrics, k-anonymat (masqué = ni valeur ni effectif),
 * objectifs écrits dans les contrats seulement, états chargement / vide / erreur / tout masqué,
 * réservée au gestionnaire (et à l'admin).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import type { ProductMetrics } from "../../src/api/types";
import { MetricsView } from "../../src/features/metrics/metrics-view";
import { formatMetricValue, periodOf, targetMet } from "../../src/features/metrics/format-metric";
import { t } from "../../src/i18n";
import { API_BASE_URL } from "../../src/lib/config";
import { SessionContext, demoToken, type DemoRole } from "../../src/lib/session";
import { server } from "../../src/mocks/node";

function renderView(role: DemoRole) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const session = { mode: "demo" as const, role, token: demoToken(role), setRole: () => undefined };
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </SessionContext.Provider>
  );
  return render(<MetricsView />, { wrapper });
}

function serve(body: Partial<ProductMetrics>) {
  server.use(
    http.get(`${API_BASE_URL}/v1/metrics/product`, () =>
      HttpResponse.json({ period_from: "2026-09-03", period_to: "2026-10-02", generated_at: "2026-10-02T09:00:00Z", k_anonymity_threshold: 5, items: [], ...body }),
    ),
  );
}

describe("formatage et objectifs", () => {
  it("taux, durées, francs ; masqué : aucune valeur", () => {
    expect(formatMetricValue({ key: "claims_review_rate", unit: "pour_dix_mille", status: "disponible", value: 3333, contributors: 6 })).toBe(t("products.percent", { value: "33,3" }));
    expect(formatMetricValue({ key: "counter_decision_display_median_ms", unit: "millisecondes", status: "disponible", value: 4200, contributors: 9 })).toBe(t("metrics.seconds", { value: "4,2" }));
    expect(formatMetricValue({ key: "claims_decision_median_ms", unit: "millisecondes", status: "disponible", value: 5_400_000, contributors: 9 })).toBe(t("metrics.hours", { value: "1,5" }));
    expect(formatMetricValue({ key: "ledger_balance_gap_xof", unit: "xof", status: "masque", value: null, contributors: null })).toBeNull();
  });

  it("objectifs du contrat seulement : < 10 s au comptoir, écart nul, aucun doublon", () => {
    expect(targetMet({ key: "counter_decision_display_median_ms", unit: "millisecondes", status: "disponible", value: 9_999, contributors: 5 })).toBe(true);
    expect(targetMet({ key: "counter_decision_display_median_ms", unit: "millisecondes", status: "disponible", value: 10_000, contributors: 5 })).toBe(false);
    expect(targetMet({ key: "ledger_balance_gap_xof", unit: "xof", status: "disponible", value: 0, contributors: 12 })).toBe(true);
    expect(targetMet({ key: "claims_review_rate", unit: "pour_dix_mille", status: "disponible", value: 10, contributors: 12 })).toBeNull();
  });

  it("période en jours locaux, bornes incluses", () => {
    expect(periodOf(30, new Date("2026-10-02T09:00:00Z"), "Africa/Abidjan")).toEqual({ from: "2026-09-03", to: "2026-10-02" });
  });
});

describe("page Mesure", () => {
  it("valeurs disponibles, indicateur masqué sans valeur ni effectif, objectif atteint", async () => {
    serve({
      items: [
        { key: "claims_review_rate", unit: "pour_dix_mille", status: "disponible", value: 3333, contributors: 6 },
        { key: "onboarding_completion_rate", unit: "pour_dix_mille", status: "masque", value: null, contributors: null },
        { key: "ledger_balance_gap_xof", unit: "xof", status: "disponible", value: 0, contributors: 14 },
      ],
    });
    renderView("gestionnaire");
    const table = await screen.findByRole("table", { name: t("metrics.tableLabel") });
    const masked = within(table).getAllByTestId("metric").find((r) => r.getAttribute("data-key") === "onboarding_completion_rate")!;
    expect(within(masked).getByText(t("metrics.masked"))).toBeTruthy();
    expect(masked.textContent).not.toMatch(/\d+ %/);
    expect(within(table).getByText(t("products.percent", { value: "33,3" }))).toBeTruthy();
    expect(within(table).getByText(t("metrics.targetMet"))).toBeTruthy();
    // L'interrupteur de mesure vit dans le menu (tous les rôles) : la page y renvoie, sans doublon.
    expect(screen.getByText(t("metrics.measureWhere"))).toBeTruthy();
    expect(screen.queryByRole("switch")).toBeNull();
  });

  it("tout masqué : explication et « Passer à 90 jours »", async () => {
    serve({ items: [{ key: "claims_review_rate", unit: "pour_dix_mille", status: "masque", value: null, contributors: null }] });
    const user = userEvent.setup();
    renderView("gestionnaire");
    const notice = await screen.findByTestId("metrics-all-masked");
    await user.click(within(notice).getByRole("button", { name: t("metrics.widen") }));
    expect(screen.getByRole("button", { name: t("metrics.period.90") }).getAttribute("aria-pressed")).toBe("true");
  });

  it("vide : que faire ensuite", async () => {
    serve({ items: [] });
    renderView("gestionnaire");
    expect(await screen.findByText(t("metrics.emptyTitle"))).toBeTruthy();
    expect(screen.getByTestId("empty-next").textContent).toContain(t("metrics.emptyNext"));
  });

  it("erreur : message de l'API, Réessayer", async () => {
    server.use(
      http.get(`${API_BASE_URL}/v1/metrics/product`, () =>
        HttpResponse.json({ code: "SYS-01", message: "Les indicateurs sont momentanément indisponibles.", action: "Réessayez dans un instant.", request_id: "req_t" }, { status: 503, headers: { "Content-Type": "application/problem+json" } }),
      ),
    );
    renderView("gestionnaire");
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Les indicateurs sont momentanément indisponibles.");
    expect(within(alert).getByRole("button", { name: t("states.retry") })).toBeTruthy();
  });

  it("serveur de démonstration : indicateurs calculés, masqués sous 5 contributeurs", async () => {
    renderView("gestionnaire");
    const rows = await screen.findAllByTestId("metric");
    expect(rows.length).toBe(9);
    expect(rows.some((r) => r.getAttribute("data-status") === "masque")).toBe(true);
    expect(rows.some((r) => r.getAttribute("data-status") === "disponible")).toBe(true);
  });

  it("médecin-conseil : page réservée", async () => {
    renderView("medecin_conseil");
    await waitFor(() => expect(screen.getByText(t("forbidden.gestionnaireOnly"))).toBeTruthy());
    expect(screen.queryByRole("table")).toBeNull();
  });
});
