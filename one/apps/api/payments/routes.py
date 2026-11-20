"""Routes L4 « cotisations » (specs/openapi.yaml, tag ``cotisations``) : route → service → dépôt.

- authentifiées (jeton, ``require_operation``) : cotisations d'un adhérent, lien de paiement,
  relance ;
- publiques (``security: []``) : page du lien et checkout ; l'organisation vient du lien ;
- webhook signé : l'organisation vient du slug de l'URL (seule exception du contrat).

Montage : ``install(app, PaymentsRuntime(clock=..., config=PaymentsConfig.from_env()))``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, Path, Request, status

from api.core.clock import Clock
from api.core.context import RequestContext, get_database, require_operation
from api.core.database import Database
from api.members.errors import MembershipError, membership_error_handler, unavailable
from api.payments.config import PaymentsConfig
from api.payments.schemas import (
    Checkout,
    CheckoutRequest,
    ContributionList,
    PaymentChannelValue,
    PaymentLink,
    PublicPaymentLink,
    QueuedMessage,
    ReminderRequest,
    WebhookAck,
)
from api.payments.service import PaymentService
from api.payments.webhooks import WebhookService

STATE_KEY: Final = "l4_payments"
WEBHOOKS_KEY: Final = "l4_webhooks"
SLUG_PATTERN: Final = r"^[a-z0-9][a-z0-9-]{1,62}$"


@dataclass(frozen=True, slots=True)
class RawNotification:
    body: bytes
    signature: str | None


@dataclass(frozen=True, slots=True)
class PaymentsRuntime:
    clock: Clock
    config: PaymentsConfig


def get_service(request: Request) -> PaymentService:
    runtime = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(runtime, PaymentsRuntime):
        raise unavailable("Le service des paiements est")
    return PaymentService(clock=runtime.clock, config=runtime.config)


def get_webhooks(request: Request) -> WebhookService:
    service = getattr(request.app.state, WEBHOOKS_KEY, None)
    if not isinstance(service, WebhookService):
        raise unavailable("La réception des paiements est")
    return service


Service = Annotated[PaymentService, Depends(get_service)]
Webhooks = Annotated[WebhookService, Depends(get_webhooks)]
DatabaseDep = Annotated[Database, Depends(get_database)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Token = Annotated[str, Path(min_length=32, max_length=128, description="Jeton du lien.")]

router = APIRouter(prefix="/v1", tags=["cotisations"])


@router.get(
    "/members/{member_id}/contributions",
    operation_id="listMemberContributions",
    status_code=status.HTTP_200_OK,
)
async def list_member_contributions(
    member_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("listMemberContributions"))],
    service: Service,
) -> ContributionList:
    return await service.list_contributions(ctx, member_id)


@router.post(
    "/members/{member_id}/reminders",
    operation_id="sendReminder",
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_reminder(
    member_id: UUID,
    body: ReminderRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("sendReminder"))],
    service: Service,
    idempotency_key: IdempotencyKey,
) -> QueuedMessage:
    return await service.send_reminder(ctx, member_id, body, idempotency_key)


@router.post(
    "/contributions/{contribution_id}/payment-links",
    operation_id="createPaymentLink",
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_link(
    contribution_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("createPaymentLink"))],
    service: Service,
    idempotency_key: IdempotencyKey,
) -> PaymentLink:
    return await service.create_link(ctx, contribution_id, idempotency_key)


@router.get(
    "/public/payment-links/{token}",
    operation_id="getPublicPaymentLink",
    status_code=status.HTTP_200_OK,
)
async def get_public_payment_link(
    token: Token, service: Service, database: DatabaseDep
) -> PublicPaymentLink:
    return await service.public_link(database, token)


@router.post(
    "/public/payment-links/{token}/checkout",
    operation_id="startCheckout",
    status_code=status.HTTP_201_CREATED,
)
async def start_checkout(
    token: Token,
    body: CheckoutRequest,
    service: Service,
    database: DatabaseDep,
    idempotency_key: IdempotencyKey,
) -> Checkout:
    return await service.checkout(database, token, body, idempotency_key)


async def raw_notification(
    request: Request, signature: Annotated[str | None, Header(alias="X-Signature")] = None
) -> RawNotification:
    """Corps BRUT (la signature porte sur les octets reçus) et en-tête de signature."""
    return RawNotification(body=await request.body(), signature=signature)


@router.post(
    "/webhooks/{organization_slug}/payments/{channel}",
    operation_id="receivePaymentWebhook",
    status_code=status.HTTP_200_OK,
)
async def receive_payment_webhook(
    organization_slug: Annotated[str, Path(pattern=SLUG_PATTERN)],
    channel: PaymentChannelValue,
    notification: Annotated[RawNotification, Depends(raw_notification)],
    webhooks: Webhooks,
    database: DatabaseDep,
) -> WebhookAck:
    return await webhooks.receive(
        database, organization_slug, channel, notification.body, notification.signature
    )


def install(app: FastAPI, runtime: PaymentsRuntime) -> None:
    """Monte les routes « cotisations » et le rendu problem+json des erreurs L4."""
    setattr(app.state, STATE_KEY, runtime)
    setattr(app.state, WEBHOOKS_KEY, WebhookService(clock=runtime.clock, config=runtime.config))
    app.include_router(router)
    app.add_exception_handler(MembershipError, membership_error_handler)
