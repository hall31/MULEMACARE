// @vitest-environment jsdom
/**
 * Palette ⌘K / Ctrl+K : accessible au clavier et au lecteur d'écran (dialog, combobox, listbox,
 * focus piégé, Échap), recherche, questions à JOE avec sources et rappel de la décision humaine,
 * brouillon de décision jamais appliqué, états hors ligne et erreur.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CommandPalette } from "../../src/features/palette/command-palette";
import { t } from "../../src/i18n";
import { API_BASE_URL } from "../../src/lib/config";
import { SessionContext, demoToken, type DemoRole } from "../../src/lib/session";
import { DEMO_CLAIM_DETAILS, DEMO_MEMBERS, REVIEW_CLAIM, medicalReasonFor } from "../../src/mocks/fixtures";
import { server } from "../../src/mocks/node";
import { demoState } from "../../src/mocks/store";

const nav = vi.hoisted(() => ({ push: vi.fn(), pathname: "/", search: "" }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: nav.push, replace: nav.push }),
  usePathname: () => nav.pathname,
  useSearchParams: () => new URLSearchParams(nav.search),
}));

function renderPalette(role: DemoRole, at: { pathname?: string; search?: string } = {}) {
  nav.pathname = at.pathname ?? "/";
  nav.search = at.search ?? "";
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const session = { mode: "demo" as const, role, token: demoToken(role), setRole: () => undefined };
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SessionContext.Provider value={session}>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </SessionContext.Provider>
  );
  return render(<CommandPalette />, { wrapper });
}

async function openWithShortcut(user: ReturnType<typeof userEvent.setup>) {
  await user.keyboard("{Control>}k{/Control}");
  const dialog = await screen.findByRole("dialog", { name: t("palette.title") });
  return { dialog, input: within(dialog).getByRole("combobox", { name: t("palette.inputLabel") }) };
}

const MEDICAL = DEMO_CLAIM_DETAILS.map((d) => medicalReasonFor(d.claim.id));

beforeEach(() => {
  nav.push.mockReset();
});

afterEach(() => {
  Object.defineProperty(window.navigator, "onLine", { configurable: true, get: () => true });
});

describe("ouverture et clavier", () => {
  it("Ctrl+K ouvre une fenêtre modale nommée, focus dans le champ combobox ; Échap ferme et rend le focus", async () => {
    const user = userEvent.setup();
    renderPalette("gestionnaire");
    const trigger = screen.getByTestId("palette-trigger");
    expect(trigger.getAttribute("aria-keyshortcuts")).toBe("Control+K Meta+K");
    const { dialog, input } = await openWithShortcut(user);
    expect(document.activeElement).toBe(input);
    expect(input.getAttribute("aria-controls")).toBe(within(dialog).getByRole("listbox").id);
    expect(dialog.getAttribute("aria-describedby")).toBeTruthy();
    // Sans texte : questions d'exemple dans un groupe nommé.
    expect(within(dialog).getByRole("group", { name: t("palette.groups.examples") })).toBeTruthy();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(trigger);
  });

  it("recherche : résultats groupés, flèches (aria-activedescendant), Entrée ouvre la fiche", async () => {
    const user = userEvent.setup();
    renderPalette("gestionnaire");
    const { dialog, input } = await openWithShortcut(user);
    await user.type(input, "Ndiaye");
    const members = await within(dialog).findByRole("group", { name: t("palette.groups.member") });
    expect(within(dialog).getByRole("group", { name: t("palette.groups.claim") })).toBeTruthy();
    const first = within(dialog).getAllByRole("option")[0]!;
    expect(input.getAttribute("aria-activedescendant")).toBe(first.id);
    expect(first.getAttribute("aria-selected")).toBe("true");
    expect(first.textContent).toContain(t("palette.ask", { q: "Ndiaye" }));
    await user.keyboard("{ArrowDown}");
    const memberOption = within(members).getAllByRole("option")[0]!;
    expect(input.getAttribute("aria-activedescendant")).toBe(memberOption.id);
    await user.keyboard("{Enter}");
    const fatou = DEMO_MEMBERS.find((m) => m.holder.family_name === "Ndiaye")!;
    expect(nav.push).toHaveBeenCalledWith(`/adherents?adherent=${fatou.id}`);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("aucun résultat : message, piste suivante, et la question à JOE reste proposée", async () => {
    const user = userEvent.setup();
    renderPalette("gestionnaire");
    const { dialog, input } = await openWithShortcut(user);
    await user.type(input, "zzzz");
    expect(await within(dialog).findByTestId("palette-empty")).toBeTruthy();
    expect(within(dialog).getByText(t("palette.noResultsNext"))).toBeTruthy();
    // Nom accessible (le monogramme « J » est décoratif, masqué aux lecteurs d'écran).
    expect(within(dialog).getAllByRole("option")).toHaveLength(1);
    expect(within(dialog).getByRole("option", { name: t("palette.ask", { q: "zzzz" }) })).toBeTruthy();
  });
});

describe("JOE", () => {
  it("réponse avec ses sources citées et « JOE recommande, la décision reste humaine »", async () => {
    const user = userEvent.setup();
    renderPalette("gestionnaire");
    const { dialog, input } = await openWithShortcut(user);
    await user.type(input, "Combien de dossiers sont en revue ?");
    await user.keyboard("{Enter}");
    const answer = await within(dialog).findByTestId("joe-answer-text");
    expect(answer.textContent).toContain(REVIEW_CLAIM.claim_number);
    const sources = within(dialog).getByTestId("joe-sources");
    expect(within(sources).getAllByRole("listitem").length).toBeGreaterThan(0);
    expect(within(dialog).getByRole("note").textContent).toBe(t("joe.humanDecision"));
    for (const medical of MEDICAL) expect(dialog.textContent).not.toContain(medical);
    // Une source « dossier » ouvre le dossier.
    await user.click(within(sources).getByRole("button", { name: REVIEW_CLAIM.claim_number }));
    expect(nav.push).toHaveBeenCalledWith(`/prises-en-charge?dossier=${REVIEW_CLAIM.id}`);
  });

  it("question médicale : refus sans source, le rappel reste affiché", async () => {
    const user = userEvent.setup();
    renderPalette("medecin_conseil");
    const { dialog, input } = await openWithShortcut(user);
    await user.type(input, "Quel est le diagnostic ?");
    await user.keyboard("{Enter}");
    await within(dialog).findByText(t("joe.refusalTitle"));
    expect(within(dialog).getByText(t("joe.noSources"))).toBeTruthy();
    expect(within(dialog).getByTestId("joe-answer").getAttribute("data-kind")).toBe("refus");
    expect(within(dialog).getByRole("note").textContent).toBe(t("joe.humanDecision"));
  });

  it("réponse sans source (interdite par le contrat) : traitée comme une erreur, jamais affichée", async () => {
    server.use(
      http.post(`${API_BASE_URL}/v1/joe/questions`, () =>
        HttpResponse.json({ ai_action_id: "6f1c2b7d-4e1a-4c33-8d9e-0a4b6c125a0e", kind: "reponse", answer: "Trois dossiers sont en revue.", sources: [] }),
      ),
    );
    const user = userEvent.setup();
    renderPalette("gestionnaire");
    const { dialog, input } = await openWithShortcut(user);
    await user.type(input, "Combien de dossiers sont en revue ?");
    await user.keyboard("{Enter}");
    const alert = await within(dialog).findByRole("alert");
    expect(alert.textContent).toContain(t("joe.unsourced.message"));
    expect(alert.textContent).toContain(t("joe.unsourced.code"));
    expect(within(alert).getByRole("button", { name: t("states.retry") })).toBeTruthy();
    expect(within(dialog).queryByTestId("joe-answer-text")).toBeNull();
    expect(dialog.textContent).not.toContain("Trois dossiers sont en revue.");
    expect(dialog.textContent).not.toContain(t("joe.noSources"));
  });

  it("brouillon de décision sans source (minItems 1 au contrat) : erreur, aucune recommandation affichée", async () => {
    server.use(
      http.post(`${API_BASE_URL}/v1/joe/decision-drafts`, () =>
        HttpResponse.json({ ai_action_id: "6f1c2b7d-4e1a-4c33-8d9e-0a4b6c125a0f", claim_id: REVIEW_CLAIM.id, recommendation: "accorder", rationale: "Sans appui.", sources: [], applied: false }),
      ),
    );
    const user = userEvent.setup();
    renderPalette("medecin_conseil", { pathname: "/prises-en-charge", search: `dossier=${REVIEW_CLAIM.id}` });
    const { dialog } = await openWithShortcut(user);
    await user.click(await within(dialog).findByText(t("palette.draft", { number: REVIEW_CLAIM.claim_number })));
    const alert = await within(dialog).findByRole("alert");
    expect(alert.textContent).toContain(t("joe.unsourced.message"));
    expect(within(dialog).queryByTestId("joe-draft-recommendation")).toBeNull();
  });

  it("médecin-conseil, dossier en revue ouvert : brouillon affiché comme brouillon, bouton qui ouvre le dossier sans jamais l'approuver", async () => {
    const user = userEvent.setup();
    const before = structuredClone(demoState().claims.find((d) => d.claim.id === REVIEW_CLAIM.id));
    renderPalette("medecin_conseil", { pathname: "/prises-en-charge", search: `dossier=${REVIEW_CLAIM.id}` });
    const { dialog } = await openWithShortcut(user);
    const draftOption = await within(dialog).findByText(t("palette.draft", { number: REVIEW_CLAIM.claim_number }));
    await user.click(draftOption);
    const panel = await within(dialog).findByTestId("joe-draft");
    expect(within(panel).getByTestId("joe-draft-badge").textContent).toBe(t("joe.draft.badge"));
    await within(panel).findByTestId("joe-draft-recommendation");
    expect(within(panel).getByText(t("joe.draft.notApplied"))).toBeTruthy();
    expect(within(panel).getByRole("note").textContent).toBe(t("joe.humanDecision"));
    // Aucun bouton de décision dans la palette.
    for (const name of [t("decision.approve"), t("decision.reject"), t("decision.requestDocuments"), /confirmer/i]) {
      expect(within(dialog).queryByRole("button", { name })).toBeNull();
    }
    await user.click(within(panel).getByRole("button", { name: t("joe.draft.open") }));
    expect(nav.push).toHaveBeenCalledWith(`/prises-en-charge?dossier=${REVIEW_CLAIM.id}`);
    expect(demoState().claims.find((d) => d.claim.id === REVIEW_CLAIM.id)).toEqual(before);
  });

  it("gestionnaire sur un dossier en revue : pas de brouillon (réservé au médecin-conseil)", async () => {
    const user = userEvent.setup();
    renderPalette("gestionnaire", { pathname: "/prises-en-charge", search: `dossier=${REVIEW_CLAIM.id}` });
    const { dialog } = await openWithShortcut(user);
    await within(dialog).findByRole("group", { name: t("palette.groups.examples") });
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(within(dialog).queryByText(t("palette.draft", { number: REVIEW_CLAIM.claim_number }))).toBeNull();
  });
});

describe("états hors ligne et erreur", () => {
  it("hors ligne : bandeau avec code, JOE indisponible (option désactivée)", async () => {
    Object.defineProperty(window.navigator, "onLine", { configurable: true, get: () => false });
    const user = userEvent.setup();
    renderPalette("gestionnaire");
    const { dialog, input } = await openWithShortcut(user);
    expect(within(dialog).getByTestId("palette-offline").textContent).toContain(t("palette.offlineCode"));
    await user.type(input, "revue");
    const ask = within(dialog).getByText(t("palette.ask", { q: "revue" })).closest("[role=option]")!;
    expect(ask.getAttribute("aria-disabled")).toBe("true");
    await user.keyboard("{Enter}");
    expect(within(dialog).queryByTestId("joe-answer")).toBeNull();
  });

  it("erreur du serveur : ce qui s'est passé, quoi faire, Réessayer", async () => {
    server.use(
      http.get(`${API_BASE_URL}/v1/search`, () =>
        HttpResponse.json(
          { code: "SYS-01", message: "La recherche est momentanément indisponible.", action: "Réessayez dans un instant.", request_id: "req_test" },
          { status: 503, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
    );
    const user = userEvent.setup();
    renderPalette("gestionnaire");
    const { dialog, input } = await openWithShortcut(user);
    await user.type(input, "Koné");
    const alert = await within(dialog).findByRole("alert");
    expect(alert.textContent).toContain("La recherche est momentanément indisponible.");
    expect(within(alert).getByRole("button", { name: t("states.retry") })).toBeTruthy();
  });
});
