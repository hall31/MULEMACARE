"""Routes L1 (tag « noyau ») : route → service → dépôt, aucune logique ici."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from api.core.context import RequestContext, require_operation
from api.core.repositories import OrganizationRepository
from api.core.schemas import (
    AuditEventList,
    AuditEventsParams,
    CreateUserRequest,
    CurrentUser,
    Organization,
    ReplaceUserRolesRequest,
    User,
    UserList,
)
from api.core.services import AuditService, OrganizationService, UserService

router = APIRouter(prefix="/v1", tags=["noyau"])

Cursor = Annotated[str | None, Query(description="Curseur opaque de la page précédente.")]
Limit = Annotated[int, Query(ge=1, le=200, description="Taille de page.")]


@router.get("/me", operation_id="getCurrentUser")
async def get_current_user(
    ctx: Annotated[RequestContext, Depends(require_operation("getCurrentUser"))],
) -> CurrentUser:
    return await UserService.for_session(ctx.session).me(ctx)


@router.get("/organization", operation_id="getCurrentOrganization")
async def get_current_organization(
    ctx: Annotated[RequestContext, Depends(require_operation("getCurrentOrganization"))],
) -> Organization:
    return await OrganizationService(OrganizationRepository(ctx.session)).current(ctx)


@router.get("/users", operation_id="listUsers")
async def list_users(
    ctx: Annotated[RequestContext, Depends(require_operation("listUsers"))],
    cursor: Cursor = None,
    limit: Limit = 50,
) -> UserList:
    return await UserService.for_session(ctx.session).list_users(ctx, cursor=cursor, limit=limit)


@router.post("/users", operation_id="createUser", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createUser"))],
) -> User:
    return await UserService.for_session(ctx.session).create(ctx, body)


@router.put("/users/{user_id}/roles", operation_id="replaceUserRoles")
async def replace_user_roles(
    user_id: UUID,
    body: ReplaceUserRolesRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("replaceUserRoles"))],
) -> User:
    return await UserService.for_session(ctx.session).replace_roles(ctx, user_id, body.roles)


@router.get("/audit-events", operation_id="listAuditEvents")
async def list_audit_events(
    ctx: Annotated[RequestContext, Depends(require_operation("listAuditEvents"))],
    params: Annotated[AuditEventsParams, Query()],
) -> AuditEventList:
    return await AuditService.for_session(ctx.session).list_events(ctx, params)
