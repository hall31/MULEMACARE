"""Routes L4 « adhérents » (specs/openapi.yaml, tag ``adherents``) : route → service → dépôt.

Montage : ``install(app, MembersRuntime(clock=..., card_keys=...))`` après ``create_app`` du
noyau. L'organisation vient du jeton via ``require_operation`` (L1), jamais de la requête.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, status

from api.core.clock import Clock
from api.core.context import RequestContext, require_operation
from api.members.cards import CardKeys
from api.members.errors import MembershipError, membership_error_handler, unavailable
from api.members.schemas import (
    AddDependentRequest,
    Card,
    ChangeMemberStatusRequest,
    CreateMemberRequest,
    Dependent,
    Entitlements,
    IssueCardRequest,
    Member,
    MemberList,
    MemberStatusValue,
)
from api.members.service import MemberService

STATE_KEY: Final = "l4_members"


@dataclass(frozen=True, slots=True)
class MembersRuntime:
    """Dépendances du module : horloge UTC et clé de scellement des secrets de carte."""

    clock: Clock
    card_keys: CardKeys


def get_runtime(request: Request) -> MembersRuntime:
    runtime = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(runtime, MembersRuntime):
        raise unavailable("Le service des adhérents est")
    return runtime


Runtime = Annotated[MembersRuntime, Depends(get_runtime)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Cursor = Annotated[str | None, Query(description="Curseur opaque de la page précédente.")]
Limit = Annotated[int, Query(ge=1, le=200, description="Taille de page.")]

router = APIRouter(prefix="/v1/members", tags=["adherents"])


def _service(ctx: RequestContext, runtime: MembersRuntime) -> MemberService:
    return MemberService(ctx=ctx, clock=runtime.clock, card_keys=runtime.card_keys)


@dataclass(frozen=True, slots=True)
class MemberQuery:
    status_filter: MemberStatusValue | None
    term: str | None
    cursor: str | None
    limit: int


def member_query(
    status_filter: Annotated[MemberStatusValue | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(min_length=2)] = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> MemberQuery:
    """Paramètres de listMembers (statut, recherche, pagination)."""
    return MemberQuery(status_filter, q, cursor, limit)


@router.get("", operation_id="listMembers", status_code=status.HTTP_200_OK)
async def list_members(
    ctx: Annotated[RequestContext, Depends(require_operation("listMembers"))],
    runtime: Runtime,
    query: Annotated[MemberQuery, Depends(member_query)],
) -> MemberList:
    return await _service(ctx, runtime).list_members(
        status_filter=query.status_filter, term=query.term, cursor=query.cursor, limit=query.limit
    )


@router.post("", operation_id="createMember", status_code=status.HTTP_201_CREATED)
async def create_member(
    body: CreateMemberRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createMember"))],
    runtime: Runtime,
    idempotency_key: IdempotencyKey,
) -> Member:
    return await _service(ctx, runtime).create(body, idempotency_key)


@router.get("/{member_id}", operation_id="getMember", status_code=status.HTTP_200_OK)
async def get_member(
    member_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("getMember"))],
    runtime: Runtime,
) -> Member:
    return await _service(ctx, runtime).get(member_id)


@router.post(
    "/{member_id}/dependents", operation_id="addDependent", status_code=status.HTTP_201_CREATED
)
async def add_dependent(
    member_id: UUID,
    body: AddDependentRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("addDependent"))],
    runtime: Runtime,
) -> Dependent:
    return await _service(ctx, runtime).add_dependent(member_id, body)


@router.get(
    "/{member_id}/entitlements",
    operation_id="getMemberEntitlements",
    status_code=status.HTTP_200_OK,
)
async def get_member_entitlements(
    member_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("getMemberEntitlements"))],
    runtime: Runtime,
    at: Annotated[date | None, Query()] = None,
) -> Entitlements:
    return await _service(ctx, runtime).entitlements(member_id, at)


@router.post("/{member_id}/cards", operation_id="issueCard", status_code=status.HTTP_201_CREATED)
async def issue_card(
    member_id: UUID,
    body: IssueCardRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("issueCard"))],
    runtime: Runtime,
    idempotency_key: IdempotencyKey,
) -> Card:
    return await _service(ctx, runtime).issue_card(member_id, body, idempotency_key)


@router.post(
    "/{member_id}/status-changes",
    operation_id="changeMemberStatus",
    status_code=status.HTTP_200_OK,
)
async def change_member_status(
    member_id: UUID,
    body: ChangeMemberStatusRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("changeMemberStatus"))],
    runtime: Runtime,
    idempotency_key: IdempotencyKey,
) -> Member:
    return await _service(ctx, runtime).change_status(member_id, body, idempotency_key)


def install(app: FastAPI, runtime: MembersRuntime) -> None:
    """Monte les routes « adhérents » et le rendu problem+json des erreurs L4."""
    setattr(app.state, STATE_KEY, runtime)
    app.include_router(router)
    app.add_exception_handler(MembershipError, membership_error_handler)
