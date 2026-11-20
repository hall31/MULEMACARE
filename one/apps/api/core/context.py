"""Dépendances FastAPI : identité → organisation injectée → utilisateur → permission.

``CurrentContext`` ouvre UNE transaction par requête, avec ``SET LOCAL ROLE mulema_app`` et
``app.organization_id`` = organisation du jeton (jamais d'un paramètre ni d'un corps). La
transaction est validée à la fin de la fonction de route, AVANT l'envoi de la réponse
(``scope="function"``) : un échec de COMMIT donne une erreur, jamais un faux succès.

Usage dans une route d'un autre lot ::

    @router.get("/v1/claims/{claim_id}")
    async def get_claim(
        claim_id: UUID,
        ctx: Annotated[RequestContext, Depends(require_operation("getClaim"))],
    ) -> Claim: ...
"""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import Database
from api.core.errors import NotAuthenticatedError
from api.core.identity import IdentityProvider
from api.core.permissions import OPERATION_ROLES, AccessScope, Principal, access_scope
from api.core.repositories import PrincipalRepository


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Ce dont un service a besoin : qui, dans quelle organisation, avec quelle transaction."""

    principal: Principal
    session: AsyncSession
    request_id: str
    access: AccessScope | None = None


_bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


def get_identity_provider(request: Request) -> IdentityProvider:
    provider: IdentityProvider = request.app.state.identity_provider
    return provider


def request_id_of(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else "req_inconnu"


async def _request_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    database: Annotated[Database, Depends(get_database)],
    identity_provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
) -> AsyncIterator[RequestContext]:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise NotAuthenticatedError
    identity = await identity_provider.authenticate(credentials.credentials)
    async with database.transaction(identity.organization_id) as session:
        principal = await PrincipalRepository(session).load(identity)
        request.state.organization_id = principal.organization_id
        request.state.user_id = principal.user_id
        yield RequestContext(
            principal=principal, session=session, request_id=request_id_of(request)
        )


CurrentContext = Annotated[RequestContext, Depends(_request_context, scope="function")]


def require_operation(operation: str) -> Callable[[RequestContext], Awaitable[RequestContext]]:
    """Dépendance : utilisateur authentifié ET autorisé (par rôle) pour ``operation``."""
    if operation not in OPERATION_ROLES:
        msg = f"opération inconnue du contrat : {operation}"
        raise LookupError(msg)

    async def dependency(ctx: CurrentContext) -> RequestContext:
        return dataclasses.replace(ctx, access=access_scope(ctx.principal, operation))

    dependency.__name__ = f"require_{operation}"
    return dependency
