"""Routes L3 (specs/openapi.yaml, tag ``grand-livre``) : route → service → dépôt.

Câblage noyau (L1), sans surcharge :
- authentification et rôles : ``require_operation("<operationId>")`` (``OPERATION_ROLES`` du
  noyau, recopie des ``x-roles`` du contrat). L'organisation vient TOUJOURS du jeton ;
- connexion : ``Database.autocommit_connection`` du noyau (même pool), en autocommit comme
  l'exige le service, qui ouvre et valide sa transaction avant la réponse.
Installées par ``api.core.app.create_app`` via ``install(app)``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, Path, Query, Request, status
from fastapi.responses import JSONResponse

from api.core.context import RequestContext, get_database, request_id_of, require_operation
from api.core.database import Database
from api.core.jsonlog import LOGGER_NAME, log_event
from api.ledger import service
from api.ledger.domain import EntryQuery, LedgerError, ReversalCommand
from api.ledger.repository import Conn
from api.ledger.schemas import (
    LedgerAccountList,
    LedgerBalance,
    LedgerEntry,
    LedgerEntryList,
    ReverseLedgerEntryRequest,
    account_out,
    balance_out,
    entry_out,
    page_out,
)

logger = logging.getLogger(f"{LOGGER_NAME}.ledger.routes")

PROBLEM_JSON: Final = "application/problem+json"
REQUEST_ID_HEADER: Final = "X-Request-ID"


async def get_ledger_connection(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[Conn]:
    """Connexion du pool du noyau, en autocommit, rendue avant l'envoi de la réponse."""
    async with database.autocommit_connection() as conn:
        yield conn


Connection = Annotated[Conn, Depends(get_ledger_connection, scope="function")]
EntryId = Annotated[UUID, Path(description="Identifiant de l'écriture.")]

router = APIRouter(prefix="/v1/ledger", tags=["grand-livre"])


def _org(ctx: RequestContext) -> UUID:
    return ctx.principal.organization_id


async def entry_query(
    account_code: Annotated[str | None, Query(pattern=r"^[0-9]{4,8}$")] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_PAGE)] = 50,
) -> EntryQuery:
    """Paramètres de requête de listLedgerEntries."""
    return EntryQuery(account_code, date_from, date_to, cursor, limit)


@router.get(
    "/accounts",
    response_model=LedgerAccountList,
    status_code=status.HTTP_200_OK,
    operation_id="listLedgerAccounts",
)
async def list_ledger_accounts(
    ctx: Annotated[RequestContext, Depends(require_operation("listLedgerAccounts"))],
    conn: Connection,
) -> LedgerAccountList:
    accounts = await service.list_accounts(conn, _org(ctx))
    return LedgerAccountList(items=[account_out(account) for account in accounts])


@router.get(
    "/entries",
    response_model=LedgerEntryList,
    status_code=status.HTTP_200_OK,
    operation_id="listLedgerEntries",
)
async def list_ledger_entries(
    ctx: Annotated[RequestContext, Depends(require_operation("listLedgerEntries"))],
    conn: Connection,
    query: Annotated[EntryQuery, Depends(entry_query)],
) -> LedgerEntryList:
    return page_out(await service.list_entries(conn, _org(ctx), query))


@router.get(
    "/entries/{entry_id}",
    response_model=LedgerEntry,
    status_code=status.HTTP_200_OK,
    operation_id="getLedgerEntry",
)
async def get_ledger_entry(
    ctx: Annotated[RequestContext, Depends(require_operation("getLedgerEntry"))],
    conn: Connection,
    entry_id: EntryId,
) -> LedgerEntry:
    return entry_out(await service.get_entry(conn, _org(ctx), entry_id))


@router.post(
    "/entries/{entry_id}/reversal",
    response_model=LedgerEntry,
    status_code=status.HTTP_201_CREATED,
    operation_id="reverseLedgerEntry",
)
async def reverse_ledger_entry(
    ctx: Annotated[RequestContext, Depends(require_operation("reverseLedgerEntry"))],
    conn: Connection,
    entry_id: EntryId,
    body: ReverseLedgerEntryRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> LedgerEntry:
    command = ReversalCommand(entry_id, body.reason, ctx.principal.user_id, idempotency_key)
    return entry_out(await service.reverse_entry(conn, _org(ctx), command))


@router.get(
    "/balance",
    response_model=LedgerBalance,
    status_code=status.HTTP_200_OK,
    operation_id="getLedgerBalance",
)
async def get_ledger_balance(
    ctx: Annotated[RequestContext, Depends(require_operation("getLedgerBalance"))],
    conn: Connection,
    at: Annotated[date | None, Query()] = None,
) -> LedgerBalance:
    return balance_out(await service.balance(conn, _org(ctx), at=at))


async def ledger_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Erreur métier → ``application/problem+json`` (code, message, action, request_id)."""
    if not isinstance(exc, LedgerError):  # pragma: no cover — enregistré pour LedgerError seul
        raise exc
    request_id = request_id_of(request)
    if exc.http_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        log_event(logger, logging.ERROR, "ledger.unavailable", code=exc.code, request_id=request_id)
    return JSONResponse(
        status_code=exc.http_status,
        media_type=PROBLEM_JSON,
        headers={REQUEST_ID_HEADER: request_id},
        content={
            "code": exc.code,
            "message": exc.message,
            "action": exc.action,
            "request_id": request_id,
        },
    )


def install(app: FastAPI) -> None:
    """Monte les routes L3 et la conversion des erreurs métier en problem+json."""
    app.include_router(router)
    app.add_exception_handler(LedgerError, ledger_error_handler)
