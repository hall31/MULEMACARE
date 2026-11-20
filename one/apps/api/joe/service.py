"""Service JOE (R11) : recommande, explique, prépare ; ne décide ni ne paie jamais.

Déroulé de chaque opération :
1. les outils de LECTURE du registre s'exécutent dans ``read_only`` (la base refuse toute
   écriture), avec les permissions de l'utilisateur ;
2. chaque lecture est inscrite dans ``ai_actions`` avec ses sources ;
3. les faits, à jetons, passent par ``ModelGateway`` (contrôle anti-identifiants, repli
   déterministe local) ; la réponse est réhydratée et cite ses sources ;
4. la réponse, le refus ou la préparation est inscrite dans ``ai_actions``.
Rien d'autre n'est écrit : un brouillon de décision n'est jamais appliqué (``applied=false``),
seul ``decideClaim`` (médecin-conseil) change l'état d'un dossier. JOE n'a aucun accès au
motif médical : une question qui le vise est refusée sans rien lire.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from api.core.clock import Clock
from api.core.context import RequestContext
from api.core.errors import NotFoundError
from api.core.pagination import decode_cursor, encode_cursor
from api.core.repositories import Keyset
from api.joe.guard import ReadOnlyScope, read_only
from api.joe.journal import AiActionJournal, JsonScalar, SourceRef, unique_sources
from api.joe.model import DeterministicModel, LanguageModel, ModelRequest, ModelTask
from api.joe.ports import MemberReaderFactory, ReadPorts
from api.joe.pseudonym import ModelGateway, Pseudonymizer, asks_medical, mask_question
from api.joe.repository import JoeReadRepository
from api.joe.schemas import (
    AiAction,
    AiActionList,
    AiActionsParams,
    DecisionDraft,
    DecisionDraftRequest,
    JoeAnswer,
    JoeQuestionRequest,
    MessageDraft,
    MessageDraftRequest,
    PageInfo,
    Source,
)
from api.joe.tools import (
    IN_REVIEW,
    Finding,
    PreparationInput,
    ToolArgs,
    run_preparation_tool,
    run_read_tool,
)

ANSWER_TOOL: Final = "repondre_question"
DECISION_TOOL: Final = "preparer_brouillon_decision"
MESSAGE_TOOL: Final = "preparer_message"

MEDICAL_REFUSAL: Final = (
    "JOE n'a pas accès au motif médical. Seul le médecin-conseil peut le lire, depuis le "
    "dossier, et chaque lecture est tracée."
)
NO_SOURCE_REFUSAL: Final = (
    "Je ne trouve aucun enregistrement pour répondre. Ouvrez un adhérent ou un dossier (⌘K), "
    "ou posez une question sur les droits, l'historique, les cotisations ou le barème."
)

# Intentions reconnues dans la question (minuscules) → outil de lecture.
_INTENTS: Final = (
    ("lire_droits", ("droit", "plafond", "couvert", "couverture", "carence", "statut", "reste")),
    ("lire_historique", ("historique", "prise en charge", "prises en charge", "soins",
                         "consomm", "dossiers")),
    ("lire_cotisations", ("cotisation", "impayé", "impaye", "retard", "relance", "échéance")),
    ("lire_bareme", ("barème", "bareme", "tarif", "prix", "coût", "cout ", "acte")),
)  # fmt: skip
MEMBER_TOOLS: Final = ("lire_adherent", "lire_droits", "lire_historique", "lire_cotisations")


@dataclass(frozen=True, slots=True)
class JoeRuntime:
    """Dépendances de JOE : horloge, modèle configuré, lecteur d'adhérents de L4."""

    clock: Clock
    model: LanguageModel
    members: MemberReaderFactory


def plan_tools(question: str, *, has_claim: bool, has_member: bool) -> list[str]:
    lowered = question.lower()
    wanted = [tool for tool, words in _INTENTS if any(w in lowered for w in words)]
    if has_member and not has_claim and not [t for t in wanted if t in MEMBER_TOOLS]:
        wanted = ["lire_adherent", "lire_droits", *wanted]
    return wanted


def _sources_out(sources: Sequence[SourceRef]) -> list[Source]:
    return [
        Source.model_validate({"type": s.type, "id": s.id, "label": s.label})
        for s in unique_sources(sources)
    ]


class JoeService:
    def __init__(self, ctx: RequestContext, runtime: JoeRuntime) -> None:
        self._ctx = ctx
        self._runtime = runtime
        org = ctx.principal.organization_id
        self._ports = ReadPorts(ctx, runtime.members(ctx))
        self._repo = JoeReadRepository(ctx.session, org)
        self._journal = AiActionJournal(ctx.session, org, ctx.principal.user_id)
        self._gateway = ModelGateway(runtime.model, fallback=DeterministicModel())

    async def _today(self) -> date:
        zone = ZoneInfo(await self._repo.timezone())
        return self._runtime.clock.now().astimezone(zone).date()

    async def _log_reads(self, findings: Sequence[Finding], args: ToolArgs) -> None:
        tool_input: dict[str, JsonScalar] = {
            "member_id": str(args.member_id) if args.member_id else None,
            "claim_id": str(args.claim_id) if args.claim_id else None,
            "at": args.at.isoformat() if args.at else None,
        }
        for finding in findings:
            await self._journal.record(
                kind="lecture", tool=finding.tool, sources=finding.sources, input=tool_input
            )

    async def _write(
        self, task: ModelTask, question: str, facts: Sequence[str], draft: str, pz: Pseudonymizer
    ) -> tuple[str, str, str]:
        """(texte pour l'utilisateur, texte à jetons pour le journal, modèle utilisé)."""
        request = ModelRequest(task=task, question=question, facts=tuple(facts), draft=draft)
        result = await self._gateway.complete(request, pz)
        return pz.rehydrate(result.text), result.text, result.model

    # --- askJoe -------------------------------------------------------------------------------

    async def ask(self, body: JoeQuestionRequest) -> JoeAnswer:
        pz = Pseudonymizer()
        ids: dict[str, JsonScalar] = {
            "claim_id": str(body.claim_id) if body.claim_id else None,
            "member_id": str(body.member_id) if body.member_id else None,
        }
        if asks_medical(body.question):
            return await self._refuse(MEDICAL_REFUSAL, mask_question(body.question, pz), ids)

        today = await self._today()
        planned = plan_tools(
            body.question,
            has_claim=body.claim_id is not None,
            has_member=body.member_id is not None,
        )
        findings: list[Finding] = []
        member_id = body.member_id
        async with read_only(self._ctx.session) as scope:
            if body.claim_id is not None:
                dossier = await self._try_read(scope, pz, "lire_dossier",
                                               ToolArgs(claim_id=body.claim_id))  # fmt: skip
                if dossier is not None:
                    findings.append(dossier)
                    member_id = member_id or dossier.member_id
            for tool in planned:
                if tool in MEMBER_TOOLS and member_id is None:
                    continue
                args = ToolArgs(member_id=member_id, at=today)
                finding = await self._try_read(scope, pz, tool, args)
                if finding is not None:
                    findings.append(finding)
        await self._log_reads(findings, ToolArgs(member_id=member_id, claim_id=body.claim_id,
                                                 at=today))  # fmt: skip

        sources = unique_sources([s for f in findings for s in f.sources])
        question = mask_question(body.question, pz)
        if not sources:
            return await self._refuse(NO_SOURCE_REFUSAL, question, ids)
        facts = [fact for f in findings for fact in f.facts]
        draft = "D'après les enregistrements consultés :\n" + "\n".join(f"- {x}" for x in facts)
        answer, stored, model = await self._write("reponse", question, facts, draft, pz)
        action = await self._journal.record(
            kind="reponse", tool=ANSWER_TOOL, sources=sources, model=model,
            input={"question": question, **ids}, output={"text": stored},
        )  # fmt: skip
        return JoeAnswer(
            ai_action_id=action, kind="reponse", answer=answer, sources=_sources_out(sources)
        )

    async def _try_read(
        self, scope: ReadOnlyScope, pz: Pseudonymizer, tool: str, args: ToolArgs
    ) -> Finding | None:
        try:
            return await run_read_tool(
                scope, principal=self._ctx.principal, ports=self._ports, pz=pz, name=tool, args=args
            )
        except NotFoundError:
            return None  # introuvable ou hors périmètre : rien à citer

    async def _refuse(self, message: str, question: str, ids: dict[str, JsonScalar]) -> JoeAnswer:
        action = await self._journal.record(
            kind="refus", tool=ANSWER_TOOL, sources=(), input={"question": question, **ids},
            output={"text": message},
        )  # fmt: skip
        return JoeAnswer(ai_action_id=action, kind="refus", answer=message, sources=[])

    # --- draftClaimDecision -------------------------------------------------------------------

    async def draft_decision(self, body: DecisionDraftRequest) -> DecisionDraft:
        pz = Pseudonymizer()
        async with read_only(self._ctx.session) as scope:
            dossier = await self._try_read(scope, pz, "lire_dossier",
                                           ToolArgs(claim_id=body.claim_id))  # fmt: skip
            if dossier is None or dossier.values.get("status") not in IN_REVIEW:
                raise NotFoundError("Aucun dossier en revue avec cet identifiant.")
            findings = [dossier]
            service_date = date.fromisoformat(dossier.values["service_date"])
            rights = await self._try_read(
                scope, pz, "lire_droits", ToolArgs(member_id=dossier.member_id, at=service_date)
            )
            if rights is not None:
                findings.append(rights)
        await self._log_reads(findings, ToolArgs(claim_id=body.claim_id, at=service_date))

        proposal = run_preparation_tool(DECISION_TOOL, PreparationInput(tuple(findings)))
        facts = [fact for f in findings for fact in f.facts]
        rationale, stored, model = await self._write(
            "brouillon_decision", "Brouillon de décision pour le médecin-conseil", facts,
            proposal.text, pz,
        )  # fmt: skip
        recommendation = proposal.recommendation or "demander_pieces"
        action = await self._journal.record(
            kind="preparation", tool=DECISION_TOOL, sources=proposal.sources, model=model,
            input={"claim_id": str(body.claim_id)},
            output={"recommendation": recommendation, "text": stored, "applied": False},
        )  # fmt: skip
        return DecisionDraft.model_validate(
            {
                "ai_action_id": action,
                "claim_id": body.claim_id,
                "recommendation": recommendation,
                "rationale": rationale,
                "sources": _sources_out(proposal.sources),
                "applied": False,
            }
        )

    # --- draftMessage -------------------------------------------------------------------------

    async def draft_message(self, body: MessageDraftRequest) -> MessageDraft:
        pz = Pseudonymizer()
        today = await self._today()
        args = ToolArgs(member_id=body.member_id, at=today)
        second = "lire_cotisations" if body.purpose == "relance_cotisation" else "lire_historique"
        async with read_only(self._ctx.session) as scope:
            member = await self._try_read(scope, pz, "lire_adherent", args)
            if member is None:
                raise NotFoundError("Adhérent introuvable.")
            findings = [member]
            extra = await self._try_read(scope, pz, second, args)
            if extra is not None:
                findings.append(extra)
        await self._log_reads(findings, args)

        proposal = run_preparation_tool(
            MESSAGE_TOOL, PreparationInput(tuple(findings), purpose=body.purpose)
        )
        facts = [fact for f in findings for fact in f.facts]
        text, stored, model = await self._write(
            "brouillon_message", f"Message : {body.purpose}", facts, proposal.text, pz
        )
        action = await self._journal.record(
            kind="preparation", tool=MESSAGE_TOOL, sources=proposal.sources, model=model,
            input={"member_id": str(body.member_id), "purpose": body.purpose},
            output={"text": stored, "channel": "sms"},
        )  # fmt: skip
        return MessageDraft.model_validate(
            {
                "ai_action_id": action,
                "channel": "sms",
                "text": text,
                "sources": _sources_out(proposal.sources),
            }
        )

    # --- listAiActions ------------------------------------------------------------------------

    async def list_actions(self, params: AiActionsParams) -> AiActionList:
        zone = ZoneInfo(await self._repo.timezone())
        before = decode_cursor(params.cursor)
        rows = await self._repo.ai_actions(
            start=datetime.combine(params.start, time.min, zone) if params.start else None,
            end=(
                datetime.combine(params.end + timedelta(days=1), time.min, zone)
                if params.end
                else None
            ),
            before=(before.at, before.id) if before else None,
            limit=params.limit + 1,
        )
        page, more = rows[: params.limit], len(rows) > params.limit
        following = Keyset(at=page[-1].occurred_at, id=page[-1].id) if more and page else None
        return AiActionList(
            items=[
                AiAction.model_validate(
                    {
                        "id": r.id,
                        "occurred_at": r.occurred_at,
                        "user_id": r.user_id,
                        "kind": r.kind,
                        "tool": r.tool,
                        "model": r.model,
                        "sources": r.sources,
                    }
                )
                for r in page
            ],
            page=PageInfo(next_cursor=encode_cursor(following)),
        )
