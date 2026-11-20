/**
 * JOE simulé (lot L8) pour la console en mode démonstration. Déterministe, en lecture seule, et
 * soumis aux mêmes garde-fous que le vrai JOE (apps/api/joe) :
 * - chaque réponse cite les enregistrements consultés (`sources`) ; sans source, un refus explicite ;
 * - aucune donnée médicale : ni motif, ni acte, ni libellé d'acte (un acte peut révéler une
 *   pathologie) ; une question médicale reçoit un refus ;
 * - un brouillon de décision n'est jamais appliqué (`applied: false`) et ne change aucun état.
 * Toutes les réponses sont validées contre specs/openapi.yaml (tests/unit/contract.test.ts).
 */
import type { AiAction, ClaimSummary, DecisionDraft, JoeAnswer, JoeQuestionRequest, Member, Role, SearchHit, Source } from "@/api/types";
import { DEMO_MEMBERS, PROVIDERS, contributionsFor, entitlementsFor } from "./fixtures";
import { demoState, nextId } from "./store";

const integer = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const money = (amount: number) => `${integer.format(amount)} FCFA`;
const today = (): string => new Date().toISOString().slice(0, 10);

const STATUS_LABEL: Record<ClaimSummary["status"], string> = {
  demandee: "demandée",
  accordee_auto: "accordée automatiquement",
  en_revue: "en revue médecin-conseil",
  pieces_demandees: "pièces demandées",
  accordee: "accordée",
  refusee: "refusée",
  payee: "payée au prestataire",
  annulee: "annulée",
};
const MEMBER_STATUS_LABEL: Record<Member["status"], string> = { actif: "actif", carence: "en carence", suspendu: "suspendu" };

const MEDICAL_QUESTION = /diagnos|motif|maladie|patholog|ordonnance|traitement|sympt|m[ée]dicament/i;

function norm(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLocaleLowerCase("fr");
}

const claims = (): ClaimSummary[] => demoState().claims.map((d) => d.claim);
const memberName = (m: Member) => `${m.holder.given_name} ${m.holder.family_name}`;
const claimSource = (c: ClaimSummary): Source => ({ type: "claim", id: c.id, label: c.claim_number });
const memberSource = (m: Member): Source => ({ type: "member", id: m.id, label: m.member_number });
const providerName = (id: string) => PROVIDERS.find((p) => p.id === id)?.name ?? "";

/** Journal de JOE (listAiActions) : chaque action avec ses sources. */
function log(userId: string, kind: AiAction["kind"], tool: string, sources: Source[]): string {
  const id = nextId();
  demoState().aiActions.push({ id, occurred_at: new Date().toISOString(), user_id: userId, kind, tool, model: "demo-local", sources });
  return id;
}

/* ------------------------------------------------------------------ recherche ⌘K */

const PER_TYPE = 5;

export function searchHits(q: string, role: Role): SearchHit[] {
  const needle = norm(q.trim());
  const hits: SearchHit[] = [];
  if (role === "gestionnaire" || role === "admin") {
    for (const m of DEMO_MEMBERS.filter((m) => norm(`${memberName(m)} ${m.member_number}`).includes(needle)).slice(0, PER_TYPE)) {
      hits.push({ type: "member", id: m.id, label: memberName(m), meta: `${m.member_number} · ${MEMBER_STATUS_LABEL[m.status]}` });
    }
  }
  for (const c of claims().filter((c) => norm(`${c.claim_number} ${c.member_display_name} ${c.provider_name}`).includes(needle)).slice(0, PER_TYPE)) {
    hits.push({ type: "claim", id: c.id, label: c.claim_number, meta: `${c.member_display_name} · ${STATUS_LABEL[c.status]}` });
  }
  for (const p of PROVIDERS.filter((p) => norm(p.name).includes(needle)).slice(0, PER_TYPE)) {
    const count = claims().filter((c) => c.provider_id === p.id).length;
    hits.push({ type: "provider", id: p.id, label: p.name, meta: `${count} prise(s) en charge` });
  }
  return hits;
}

/* ------------------------------------------------------------------ questions */

function claimAnswer(c: ClaimSummary): { answer: string; sources: Source[] } {
  const member = DEMO_MEMBERS.find((m) => m.id === c.member_id);
  const rule = c.rule ? ` Règle ${c.rule.code} v${c.rule.version}` : "";
  const why = c.rule?.code === "R-20" ? " : au-dessus du seuil d'accord automatique, la revue du médecin-conseil est requise." : ".";
  return {
    answer: `Dossier ${c.claim_number} (${c.member_display_name}, ${providerName(c.provider_id)}) : ${STATUS_LABEL[c.status]}, ${money(c.total_xof)} dont ${money(c.covered_xof)} à la charge de la mutuelle.${rule}${why}`,
    sources: [claimSource(c), ...(member ? [memberSource(member)] : [])],
  };
}

function memberAnswer(m: Member): { answer: string; sources: Source[] } {
  const late = contributionsFor(m).filter((c) => c.status === "en_retard");
  const ent = entitlementsFor(m, today());
  const lateText = late.length === 0 ? "cotisations à jour" : `${late.length} cotisation(s) en retard`;
  return {
    answer: `Adhérent ${m.member_number} (${memberName(m)}) : ${MEMBER_STATUS_LABEL[m.status]}, formule ${m.plan_code}, ${lateText}. Plafond familial consommé : ${money(ent.consumed_xof)} sur ${money(ent.family_annual_ceiling_xof)}.`,
    sources: [memberSource(m), ...late.map((c): Source => ({ type: "contribution", id: c.id, label: `Cotisation ${c.period_start.slice(0, 7)}` })), { type: "plan_version", id: ent.plan_version_id, label: m.plan_code }],
  };
}

function compose(input: JoeQuestionRequest): { kind: JoeAnswer["kind"]; answer: string; sources: Source[] } {
  const q = norm(input.question);
  const refusal = (answer: string) => ({ kind: "refus" as const, answer, sources: [] });

  if (MEDICAL_QUESTION.test(input.question)) {
    return refusal("Je ne lis aucune donnée médicale. Le motif d'un soin se consulte dans le dossier, par le médecin-conseil seulement, et chaque lecture est journalisée.");
  }

  const byNumber = /pec-\d{2}-\d{5}/.exec(q)?.[0];
  const claim = claims().find((c) => c.id === input.claim_id) ?? claims().find((c) => byNumber && norm(c.claim_number) === byNumber);
  if (claim) return { kind: "reponse", ...claimAnswer(claim) };

  const byMember = /mc-\d{8}/.exec(q)?.[0];
  const member = DEMO_MEMBERS.find((m) => m.id === input.member_id) ?? DEMO_MEMBERS.find((m) => byMember && norm(m.member_number) === byMember);
  if (member) return { kind: "reponse", ...memberAnswer(member) };

  const provider = PROVIDERS.find((p) => q.includes(norm(p.name)));
  if (provider) {
    const list = claims().filter((c) => c.provider_id === provider.id);
    if (list.length === 0) return refusal(`Aucune prise en charge enregistrée pour ${provider.name}.`);
    return {
      kind: "reponse",
      answer: `${list.length} prise(s) en charge pour ${provider.name} : ${list.map((c) => `${c.claim_number} (${STATUS_LABEL[c.status]})`).join(", ")}.`,
      sources: [{ type: "provider", id: provider.id, label: provider.name }, ...list.map(claimSource)],
    };
  }

  if (/revue/.test(q)) {
    const list = claims().filter((c) => c.status === "en_revue");
    if (list.length === 0) return refusal("Aucun dossier n'est en revue : rien à vérifier pour l'instant.");
    return { kind: "reponse", answer: `${list.length} dossier(s) en revue médecin-conseil : ${list.map((c) => c.claim_number).join(", ")}. Seul le médecin-conseil décide.`, sources: list.map(claimSource) };
  }

  if (/impaye|retard|cotisation/.test(q)) {
    const late = DEMO_MEMBERS.map((m) => ({ m, late: contributionsFor(m).filter((c) => c.status === "en_retard") })).filter((x) => x.late.length > 0);
    if (late.length === 0) return refusal("Aucune cotisation en retard dans les données consultées.");
    return {
      kind: "reponse",
      answer: `${late.length} adhérent(s) avec des cotisations en retard : ${late.map((x) => `${x.m.member_number} (${x.late.length} échéance(s), ${MEMBER_STATUS_LABEL[x.m.status]})`).join(", ")}.`,
      sources: late.flatMap((x) => [memberSource(x.m), ...x.late.map((c): Source => ({ type: "contribution", id: c.id, label: `Cotisation ${c.period_start.slice(0, 7)}` }))]),
    };
  }

  if (/fraude|alerte/.test(q)) {
    const list = claims().filter((c) => c.fraud_flagged);
    if (list.length === 0) return refusal("Aucune alerte fraude dans les données consultées.");
    return { kind: "reponse", answer: `${list.length} dossier(s) avec une alerte fraude, bloqués avant paiement : ${list.map((c) => c.claim_number).join(", ")}.`, sources: list.map(claimSource) };
  }

  return refusal("Je n'ai trouvé aucun enregistrement pour répondre. Précisez un numéro de dossier (PEC-…), d'adhérent (MC-…) ou un prestataire.");
}

export function joeAnswer(input: JoeQuestionRequest, userId: string): JoeAnswer {
  const { kind, answer, sources } = compose(input);
  const id = log(userId, kind, "repondre", sources);
  return { ai_action_id: id, kind, answer, sources };
}

/* ------------------------------------------------------------------ brouillon de décision */

export function decisionDraft(claimId: string, userId: string): DecisionDraft | null {
  const detail = demoState().claims.find((d) => d.claim.id === claimId);
  if (!detail) return null;
  const c = detail.claim;
  const member = DEMO_MEMBERS.find((m) => m.id === c.member_id);
  const ent = member ? entitlementsFor(member, today()) : null;
  const sources: Source[] = [claimSource(c), ...(member ? [memberSource(member)] : []), ...(ent ? [{ type: "plan_version" as const, id: ent.plan_version_id, label: member?.plan_code ?? "" }] : [])];

  let recommendation: DecisionDraft["recommendation"];
  let rationale: string;
  if (c.fraud_flagged) {
    recommendation = "demander_pieces";
    rationale = "Alerte fraude sur le dossier : demander les pièces justificatives avant toute décision.";
  } else if (member && member.status !== "actif") {
    recommendation = "refuser";
    rationale = `Adhérent ${MEMBER_STATUS_LABEL[member.status]} à la date du soin : les droits ne sont pas ouverts (règle R-01).`;
  } else if (ent && ent.remaining_xof < c.covered_xof) {
    recommendation = "refuser";
    rationale = `Plafond familial restant (${money(ent.remaining_xof)}) inférieur à la part mutuelle demandée (${money(c.covered_xof)}) (règle R-09).`;
  } else {
    recommendation = "accorder";
    rationale = `Droits ouverts, prestataire du réseau, montant au barème et plafond familial suffisant (${ent ? money(ent.remaining_xof) : "—"} restants). Le dossier est en revue parce qu'il dépasse le seuil d'accord automatique (R-20).`;
  }
  const id = log(userId, "preparation", "brouillon_decision", sources);
  return { ai_action_id: id, claim_id: c.id, recommendation, rationale, sources, applied: false };
}
