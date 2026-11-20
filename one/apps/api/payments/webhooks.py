"""Webhook de paiement (``receivePaymentWebhook``) : signature, idempotence, droits ouverts.

Ordre des contrôles :
1. canal activé (sinon 404) puis signature HMAC du corps BRUT (sinon 401 PAY-01) : rien n'est
   lu ni écrit en base pour une notification non signée ;
2. corps conforme à ``PaymentWebhookRequest`` (sinon 422) ;
3. dans UNE transaction sous ``mulema_app`` : organisation résolue par la fonction SECURITY
   DEFINER du contrat, clé d'idempotence ``webhook:<canal>`` / ``event_id`` réservée (barrière 1),
   paiement verrouillé ``FOR UPDATE`` et contrôlé (barrière 2 : un paiement déjà confirmé ne
   compte jamais deux fois), puis cotisation réglée, événement ``contribution.received`` et
   réouverture des droits (``member.status_changed``) — tout est visible au COMMIT, avant la
   réponse 200 : R2 (« moins de 60 s ») est tenu par construction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import Clock
from api.core.database import Database
from api.core.jsonlog import log_event
from api.members import outbox
from api.members.errors import (
    FieldProblem,
    MembershipError,
    amount_mismatch,
    bad_signature,
    not_found,
    state_conflict,
)
from api.members.idempotency import IdempotencyStore, KeyRequest, fingerprint
from api.members.repository import MemberRepository
from api.members.status import reopen_after_payment
from api.payments.config import PaymentsConfig
from api.payments.repository import PaymentRecord, PaymentRepository
from api.payments.schemas import PaymentWebhookRequest, WebhookAck

logger = logging.getLogger("mulema.payments.webhooks")

_FINAL: Final = frozenset({"confirme", "echoue"})


def _parse(body: bytes) -> PaymentWebhookRequest:
    try:
        return PaymentWebhookRequest.model_validate_json(body)
    except ValidationError as exc:
        errors = tuple(
            FieldProblem(
                ".".join(str(p) for p in e["loc"]) or "corps", "Valeur manquante ou invalide."
            )
            for e in exc.errors()
        )
        raise MembershipError(
            "VAL-01",
            422,
            "La notification de paiement est mal formée.",
            "Corrigez le format de la notification chez le canal.",
            errors=errors,
        ) from exc


@dataclass(frozen=True, slots=True)
class WebhookService:
    clock: Clock
    config: PaymentsConfig

    async def receive(
        self,
        database: Database,
        slug: str,
        channel_name: str,
        body: bytes,
        signature: str | None,
    ) -> WebhookAck:
        channel = self.config.channels.get(channel_name)
        if channel is None:
            raise not_found()
        if not channel.verify_signature(body, signature):
            log_event(
                logger, logging.WARNING, "payments.webhook_bad_signature", channel=channel_name
            )
            raise bad_signature()
        notification = _parse(body)
        request_hash = fingerprint(notification.model_dump(mode="json"))
        async with database.transaction(None) as session:
            return await self.apply(session, slug, channel_name, notification, request_hash)

    async def apply(
        self,
        session: AsyncSession,
        slug: str,
        channel_name: str,
        notification: PaymentWebhookRequest,
        request_hash: str,
    ) -> WebhookAck:
        """Effets d'une notification authentifiée, dans la transaction ``session``."""
        payments = PaymentRepository(session)
        org = await payments.resolve_organization(slug)
        if org is None:
            raise not_found()
        await payments.enter_organization(org)
        now = self.clock.now()
        request = KeyRequest(f"webhook:{channel_name}", notification.event_id, request_hash)
        keys = IdempotencyStore(session)
        stored = await keys.begin(org, request, now=now, ttl=self.config.webhook_key_ttl)
        if stored is not None:
            log_event(
                logger,
                logging.INFO,
                "payments.webhook_replayed",
                organization_id=org,
                channel=channel_name,
            )
            return WebhookAck(received=True, duplicate=True)
        duplicate = await self._settle(session, payments, org, channel_name, notification)
        ack = WebhookAck(received=True, duplicate=duplicate)
        await keys.complete(org, request, 200, ack.model_dump())
        return ack

    async def _settle(
        self,
        session: AsyncSession,
        payments: PaymentRepository,
        org: UUID,
        channel_name: str,
        notification: PaymentWebhookRequest,
    ) -> bool:
        """Applique la notification ; renvoie vrai si elle était déjà appliquée (aucun effet)."""
        payment = await payments.payment(org, notification.merchant_reference, lock=True)
        if (
            payment is None
            or payment.channel != channel_name
            or payment.provider_reference != notification.provider_reference
        ):
            raise not_found()
        if payment.status in _FINAL:
            if payment.status == notification.status:
                return True
            raise state_conflict(
                "Ce paiement a déjà un résultat définitif différent.",
                "Vérifiez la transaction chez le canal de paiement.",
            )
        if notification.amount_xof != payment.amount_xof:
            log_event(
                logger,
                logging.WARNING,
                "payments.webhook_amount_mismatch",
                organization_id=org,
                payment_id=payment.id,
            )
            raise amount_mismatch()
        now = self.clock.now()
        if notification.status == "echoue":
            await payments.set_payment_status(org, payment.id, "echoue", None)
            return False
        await payments.set_payment_status(org, payment.id, "confirme", now)
        await self._apply_to_contribution(session, payments, org, payment)
        return False

    async def _apply_to_contribution(
        self,
        session: AsyncSession,
        payments: PaymentRepository,
        org: UUID,
        payment: PaymentRecord,
    ) -> None:
        if payment.contribution_id is None:
            return
        contribution = await payments.contribution(org, payment.contribution_id, lock=True)
        if contribution is None:
            raise not_found()
        if contribution.status not in {"a_payer", "en_retard"}:
            # Deux paiements pour une même échéance : le second est encaissé sans être
            # recompté (aucun événement) ; à traiter par le gestionnaire (Q-L4-07).
            log_event(
                logger,
                logging.WARNING,
                "payments.contribution_already_settled",
                organization_id=org,
                payment_id=payment.id,
                contribution_id=contribution.id,
            )
            return
        now = self.clock.now()
        await payments.mark_contribution_paid(org, contribution.id, now)
        await payments.mark_links_used(org, contribution.id, now)
        payload: dict[str, object] = {
            "contribution_id": str(contribution.id),
            "payment_id": str(payment.id),
            "member_id": str(contribution.member_id),
            "period_start": outbox.iso_date(contribution.period_start),
            "amount_xof": payment.amount_xof,
            "currency": "XOF",
            "channel": payment.channel,
            "payer_kind": payment.payer_kind,
            "payer_country_code": payment.payer_country_code,
            "confirmed_at": outbox.rfc3339(now),
        }
        await outbox.emit(
            session,
            outbox.NewEvent(org, "contribution.received", contribution.id, payload, now),
        )
        await reopen_after_payment(
            MemberRepository(session), org=org, member_id=contribution.member_id, now=now
        )
        log_event(
            logger,
            logging.INFO,
            "payments.contribution_received",
            organization_id=org,
            payment_id=payment.id,
            contribution_id=contribution.id,
        )
