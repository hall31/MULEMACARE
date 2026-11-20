"""Routes P1 « espace adhérent et diaspora » (tag ``espace-adherent``) : route → service → dépôt.

Rôle ``adherent`` seulement (``require_operation``, L1). Le contrat consulté vient du jeton ;
aucune route ne reçoit d'identifiant d'adhérent. Les dépendances existantes sont réutilisées
(runtime L4 des adhérents, service L4 des paiements) : aucun nouveau gabarit de dépendance.
Montage : ``install(app)`` APRÈS ``install`` des modules ``members`` et ``payments``.
"""

from __future__ import annotations

from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Response, status

from api.core.context import RequestContext, require_operation
from api.member_space.schemas import (
    ClaimTracking,
    MyBeneficiaryList,
    MyCard,
    MyClaimList,
    MyContributions,
)
from api.member_space.service import MemberSpaceService
from api.members.routes import MembersRuntime, get_runtime
from api.payments.routes import get_service
from api.payments.schemas import PaymentLink
from api.payments.service import PaymentService

# Le QR est un titre d'accès : jamais en cache (navigateur, mandataire).
NO_STORE: Final = {"Cache-Control": "no-store", "Pragma": "no-cache"}

Runtime = Annotated[MembersRuntime, Depends(get_runtime)]
Payments = Annotated[PaymentService, Depends(get_service)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Cursor = Annotated[str | None, Query(description="Curseur opaque de la page précédente.")]
Limit = Annotated[int, Query(ge=1, le=200, description="Taille de page.")]

router = APIRouter(prefix="/v1/me", tags=["espace-adherent"])


def _service(ctx: RequestContext, runtime: MembersRuntime) -> MemberSpaceService:
    return MemberSpaceService(ctx=ctx, clock=runtime.clock, card_keys=runtime.card_keys)


@router.get("/card", operation_id="getMyCard", status_code=status.HTTP_200_OK)
async def get_my_card(
    response: Response,
    ctx: Annotated[RequestContext, Depends(require_operation("getMyCard"))],
    runtime: Runtime,
    person_id: Annotated[UUID | None, Query(description="Bénéficiaire du contrat.")] = None,
) -> MyCard:
    card = await _service(ctx, runtime).card(person_id)
    response.headers.update(NO_STORE)
    return card


@router.get("/beneficiaries", operation_id="listMyBeneficiaries", status_code=status.HTTP_200_OK)
async def list_my_beneficiaries(
    ctx: Annotated[RequestContext, Depends(require_operation("listMyBeneficiaries"))],
    runtime: Runtime,
) -> MyBeneficiaryList:
    return await _service(ctx, runtime).beneficiaries()


@router.get("/claims", operation_id="listMyClaims", status_code=status.HTTP_200_OK)
async def list_my_claims(
    ctx: Annotated[RequestContext, Depends(require_operation("listMyClaims"))],
    runtime: Runtime,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> MyClaimList:
    return await _service(ctx, runtime).claims(cursor, limit)


@router.get(
    "/claims/{claim_id}/tracking",
    operation_id="getMyClaimTracking",
    status_code=status.HTTP_200_OK,
)
async def get_my_claim_tracking(
    claim_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("getMyClaimTracking"))],
    runtime: Runtime,
) -> ClaimTracking:
    return await _service(ctx, runtime).tracking(claim_id)


@router.get("/contributions", operation_id="listMyContributions", status_code=status.HTTP_200_OK)
async def list_my_contributions(
    ctx: Annotated[RequestContext, Depends(require_operation("listMyContributions"))],
    runtime: Runtime,
) -> MyContributions:
    return await _service(ctx, runtime).contributions()


@router.post(
    "/contributions/{contribution_id}/payment-links",
    operation_id="createMyPaymentLink",
    status_code=status.HTTP_201_CREATED,
)
async def create_my_payment_link(
    contribution_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("createMyPaymentLink"))],
    runtime: Runtime,
    payments: Payments,
    idempotency_key: IdempotencyKey,
) -> PaymentLink:
    return await _service(ctx, runtime).invite_payer(payments, contribution_id, idempotency_key)


def install(app: FastAPI) -> None:
    """Monte l'espace adhérent (les erreurs L4 sont déjà rendues par ``members``/``payments``)."""
    app.include_router(router)
