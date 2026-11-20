"""Routes L8 (tag ``joe``) : route → service → dépôt. Aucune route ne décide ni ne paie.

Montage (câblage dans ``api.core.app`` par l'intégration, pas par ce lot) ::

    install(app, JoeRuntime(clock=..., model=build_language_model(
        JoeModelSettings.from_env(os.environ)), members=member_reader_factory(clock, card_keys)))

L'organisation et les rôles viennent du jeton (``require_operation``, L1).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query, Request

from api.core.context import RequestContext, require_operation
from api.joe.schemas import (
    AiActionList,
    AiActionsParams,
    DecisionDraft,
    DecisionDraftRequest,
    JoeAnswer,
    JoeQuestionRequest,
    MessageDraft,
    MessageDraftRequest,
    SearchResults,
)
from api.joe.search import search as run_search
from api.joe.service import JoeRuntime, JoeService

__all__ = ["JoeRuntime", "install", "router"]

router = APIRouter(prefix="/v1", tags=["joe"])


def get_runtime(request: Request) -> JoeRuntime:
    runtime: JoeRuntime = request.app.state.joe_runtime
    return runtime


Runtime = Annotated[JoeRuntime, Depends(get_runtime)]


@router.post("/joe/questions", operation_id="askJoe")
async def ask_joe(
    body: JoeQuestionRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("askJoe"))],
    runtime: Runtime,
) -> JoeAnswer:
    return await JoeService(ctx, runtime).ask(body)


@router.post("/joe/decision-drafts", operation_id="draftClaimDecision")
async def draft_claim_decision(
    body: DecisionDraftRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("draftClaimDecision"))],
    runtime: Runtime,
) -> DecisionDraft:
    return await JoeService(ctx, runtime).draft_decision(body)


@router.post("/joe/message-drafts", operation_id="draftMessage")
async def draft_message(
    body: MessageDraftRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("draftMessage"))],
    runtime: Runtime,
) -> MessageDraft:
    return await JoeService(ctx, runtime).draft_message(body)


@router.get("/search", operation_id="search")
async def search(
    q: Annotated[str, Query(min_length=2, max_length=200, description="Texte recherché.")],
    ctx: Annotated[RequestContext, Depends(require_operation("search"))],
) -> SearchResults:
    return await run_search(ctx, q)


@router.get("/ai-actions", operation_id="listAiActions")
async def list_ai_actions(
    ctx: Annotated[RequestContext, Depends(require_operation("listAiActions"))],
    params: Annotated[AiActionsParams, Query()],
    runtime: Runtime,
) -> AiActionList:
    return await JoeService(ctx, runtime).list_actions(params)


def install(app: FastAPI, runtime: JoeRuntime) -> None:
    """Monte les routes L8 et le runtime de JOE."""
    app.state.joe_runtime = runtime
    app.include_router(router)
