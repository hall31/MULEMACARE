/**
 * Garde-fous de JOE dans le serveur de démonstration (R11, PRD §5, POLISH_CONTRACT §12.7) :
 * - toute réponse cite ses sources, sinon c'est un refus explicite ;
 * - aucune donnée médicale (motif, acte, libellé d'acte) dans une réponse ou un brouillon ;
 * - un brouillon de décision n'est jamais appliqué et ne change pas le dossier ;
 * - chaque action est journalisée avec ses sources (ai_actions).
 */
import { describe, expect, it } from "vitest";
import type { DecisionDraft, JoeAnswer, SearchResults } from "../../src/api/types";
import { API_BASE_URL } from "../../src/lib/config";
import { demoToken, type DemoRole } from "../../src/lib/session";
import { DEMO_CLAIM_DETAILS, DEMO_MEMBERS, REVIEW_CLAIM, medicalReasonFor } from "../../src/mocks/fixtures";
import { demoState } from "../../src/mocks/store";

async function post<T>(role: DemoRole, path: string, body: unknown): Promise<{ status: number; body: T }> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${demoToken(role)}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: (await res.json()) as T };
}

const MEDICAL_STRINGS = [
  ...DEMO_CLAIM_DETAILS.map((d) => medicalReasonFor(d.claim.id)),
  ...DEMO_CLAIM_DETAILS.flatMap((d) => d.items.map((i) => i.label)),
];

function expectNoMedical(text: string) {
  for (const medical of MEDICAL_STRINGS) expect(text, medical).not.toContain(medical);
  expect(text).not.toMatch(/donnée fictive|diagnostic :|motif :/i);
}

const QUESTIONS = [
  "Combien de dossiers sont en revue ?",
  "Quels adhérents sont en impayé ?",
  "Y a-t-il des alertes fraude ?",
  `Où en est le dossier ${REVIEW_CLAIM.claim_number} ?`,
  `Que sait-on de l'adhérent ${DEMO_MEMBERS[3]!.member_number} ?`,
  "Prises en charge de Laboratoire Marcory Centre",
  "Quelle est la couleur du ciel ?",
];

describe("JOE : réponses sourcées, sans donnée médicale", () => {
  it.each(QUESTIONS)("« %s »", async (question) => {
    const { status, body } = await post<JoeAnswer>("gestionnaire", "/v1/joe/questions", { question });
    expect(status).toBe(200);
    if (body.kind === "reponse") expect(body.sources.length).toBeGreaterThan(0);
    else expect(body.sources).toEqual([]);
    expectNoMedical(body.answer);
    for (const source of body.sources) expectNoMedical(source.label ?? "");
  });

  it("question sans enregistrement : refus explicite, sans source", async () => {
    const { body } = await post<JoeAnswer>("gestionnaire", "/v1/joe/questions", { question: "Quelle est la couleur du ciel ?" });
    expect(body.kind).toBe("refus");
  });

  it("question médicale : refus, même pour le médecin-conseil (le motif se lit dans le dossier, audité)", async () => {
    const { body } = await post<JoeAnswer>("medecin_conseil", "/v1/joe/questions", { question: "Quel est le diagnostic du dossier ?", claim_id: REVIEW_CLAIM.id });
    expect(body.kind).toBe("refus");
    expect(body.sources).toEqual([]);
  });

  it("contexte du dossier ouvert : la réponse cite ce dossier", async () => {
    const { body } = await post<JoeAnswer>("medecin_conseil", "/v1/joe/questions", { question: "Où en est-il ?", claim_id: REVIEW_CLAIM.id });
    expect(body.kind).toBe("reponse");
    expect(body.sources[0]).toMatchObject({ type: "claim", id: REVIEW_CLAIM.id, label: REVIEW_CLAIM.claim_number });
  });
});

describe("JOE : brouillon de décision", () => {
  it("jamais appliqué, ne change ni le statut ni les décisions du dossier, journalisé avec ses sources", async () => {
    const before = structuredClone(demoState().claims.find((d) => d.claim.id === REVIEW_CLAIM.id));
    const { status, body } = await post<DecisionDraft>("medecin_conseil", "/v1/joe/decision-drafts", { claim_id: REVIEW_CLAIM.id });
    expect(status).toBe(200);
    expect(body.applied).toBe(false);
    expect(["accorder", "refuser", "demander_pieces"]).toContain(body.recommendation);
    expect(body.sources.length).toBeGreaterThan(0);
    expectNoMedical(body.rationale);
    expect(demoState().claims.find((d) => d.claim.id === REVIEW_CLAIM.id)).toEqual(before);
    expect(demoState().ledger.some((e) => e.source_id === REVIEW_CLAIM.id && e.label.includes("revue"))).toBe(false);
    expect(demoState().aiActions.at(-1)).toMatchObject({ id: body.ai_action_id, kind: "preparation", sources: body.sources });
  });

  it("réservé au médecin-conseil (x-roles)", async () => {
    const { status } = await post<unknown>("gestionnaire", "/v1/joe/decision-drafts", { claim_id: REVIEW_CLAIM.id });
    expect(status).toBe(403);
  });
});

describe("recherche ⌘K", () => {
  it("le gestionnaire trouve adhérents, dossiers et prestataires ; le médecin-conseil pas les fiches adhérent", async () => {
    const get = async (role: DemoRole, q: string) =>
      (await (await fetch(`${API_BASE_URL}/v1/search?q=${encodeURIComponent(q)}`, { headers: { Authorization: `Bearer ${demoToken(role)}` } })).json()) as SearchResults;
    const forManager = await get("gestionnaire", "Ndiaye");
    expect(forManager.items.map((h) => h.type)).toEqual(expect.arrayContaining(["member", "claim"]));
    const forDoctor = await get("medecin_conseil", "Ndiaye");
    expect(forDoctor.items.some((h) => h.type === "member")).toBe(false);
    expect((await get("gestionnaire", "Palmiers")).items.some((h) => h.type === "provider")).toBe(true);
    for (const hit of forManager.items) expectNoMedical(`${hit.label} ${hit.meta ?? ""}`);
  });
});
