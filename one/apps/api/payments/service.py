"""Cotisations, liens de paiement diaspora, checkout public et relances (R2, R8).

Deux familles d'appelants :
- authentifiés (gestionnaire, admin) : organisation du jeton, transaction de la requête ;
- publics (payeur diaspora) : l'organisation est résolue depuis le jeton du lien par la
  fonction SECURITY DEFINER du contrat, puis positionnée pour toute la transaction.

Toute commande de paiement est idempotente (clé stockée dans ``idempotency_keys``).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from api.core.clock import Clock
from api.core.context import RequestContext
from api.core.database import Database
from api.core.jsonlog import log_event
from api.members.errors import invalid, link_gone, not_found, state_conflict
from api.members.idempotency import IdempotencyStore, KeyRequest, fingerprint
from api.payments.channels import CheckoutOrder
from api.payments.config import PaymentsConfig
from api.payments.links import initials, token_for, token_hash
from api.payments.repository import (
    ContributionRecord,
    NewMessage,
    NewPayment,
    PaymentRepository,
)
from api.payments.schemas import (
    Checkout,
    CheckoutRequest,
    Contribution,
    ContributionList,
    PaymentLink,
    PublicPaymentLink,
    QueuedMessage,
    ReminderRequest,
)

logger = logging.getLogger("mulema.payments")

SCOPE_LINK: Final = "command:payment_link.create"
# Espace adhérent (P1) : portée distincte, empreinte qui porte aussi le contrat.
SCOPE_MEMBER_LINK: Final = "command:payment_link.create_by_member"
SCOPE_CHECKOUT: Final = "command:payment.checkout"
SCOPE_REMINDER: Final = "command:member.reminder"
PAYABLE: Final = frozenset({"a_payer", "en_retard"})
LINK_PAYER_KIND: Final = "proche"


def _contribution_out(record: ContributionRecord) -> Contribution:
    return Contribution.model_validate(
        {
            "id": record.id,
            "period_start": record.period_start,
            "due_on": record.due_on,
            "amount_xof": record.amount_xof,
            "status": record.status,
            "paid_at": record.paid_at,
            "channel": record.channel,
        }
    )


@dataclass(frozen=True, slots=True)
class PaymentService:
    clock: Clock
    config: PaymentsConfig

    # --- Gestionnaire (authentifié) --------------------------------------------------------

    async def list_contributions(self, ctx: RequestContext, member_id: UUID) -> ContributionList:
        org = ctx.principal.organization_id
        repo = PaymentRepository(ctx.session)
        if await repo.holder_contact(org, member_id) is None:
            raise not_found()
        return ContributionList(
            items=[_contribution_out(c) for c in await repo.contributions_of(org, member_id)]
        )

    async def _new_link(
        self, repo: PaymentRepository, org: UUID, contribution_id: UUID
    ) -> tuple[UUID, PaymentLink]:
        link_id = uuid.uuid4()
        token = token_for(self.config.link_secret, link_id)
        ttl = int(self.config.link_ttl.total_seconds())
        expires_at = await repo.insert_link(org, link_id, contribution_id, token_hash(token), ttl)
        return link_id, PaymentLink(
            url=f"{self.config.public_base_url}/{token}", expires_at=expires_at
        )

    async def create_link(
        self, ctx: RequestContext, contribution_id: UUID, idempotency_key: str
    ) -> PaymentLink:
        request = KeyRequest(
            SCOPE_LINK, idempotency_key, fingerprint({"contribution_id": str(contribution_id)})
        )
        return await self._create_link(ctx, contribution_id, request)

    async def create_member_link(
        self, ctx: RequestContext, member_id: UUID, contribution_id: UUID, idempotency_key: str
    ) -> PaymentLink:
        """« Inviter un proche à payer » (P1) : même flux, sur une cotisation de SON contrat.

        L'appartenance est vérifiée AVANT la réservation de la clé : rejouer la clé d'un autre
        adhérent sur sa cotisation ne renvoie jamais son lien (NOT-01, rien n'est écrit).
        """
        org = ctx.principal.organization_id
        owned = await PaymentRepository(ctx.session).contribution(org, contribution_id)
        if owned is None or owned.member_id != member_id:
            raise not_found()
        request = KeyRequest(
            SCOPE_MEMBER_LINK,
            idempotency_key,
            fingerprint({"contribution_id": str(contribution_id), "member_id": str(member_id)}),
        )
        return await self._create_link(ctx, contribution_id, request)

    async def _create_link(
        self, ctx: RequestContext, contribution_id: UUID, request: KeyRequest
    ) -> PaymentLink:
        org = ctx.principal.organization_id
        repo = PaymentRepository(ctx.session)
        keys = IdempotencyStore(ctx.session)
        stored = await keys.begin(org, request, now=self.clock.now())
        if stored is not None:
            link_id = UUID(str(stored.body["link_id"]))
            found = await repo.link(org, link_id)
            if found is None:
                raise not_found()
            token = token_for(self.config.link_secret, link_id)
            return PaymentLink(url=f"{self.config.public_base_url}/{token}", expires_at=found[1])
        contribution = await repo.contribution(org, contribution_id, lock=True)
        if contribution is None:
            raise not_found()
        if contribution.status not in PAYABLE:
            raise state_conflict(
                "Cette cotisation est déjà réglée ou annulée.",
                "Aucun lien n'est nécessaire ; consultez les cotisations de l'adhérent.",
            )
        link_id, link = await self._new_link(repo, org, contribution_id)
        await keys.complete(org, request, 201, {"link_id": str(link_id)})
        return link

    async def send_reminder(
        self, ctx: RequestContext, member_id: UUID, body: ReminderRequest, idempotency_key: str
    ) -> QueuedMessage:
        org = ctx.principal.organization_id
        repo = PaymentRepository(ctx.session)
        keys = IdempotencyStore(ctx.session)
        now = self.clock.now()
        request = KeyRequest(
            SCOPE_REMINDER,
            idempotency_key,
            fingerprint({"member_id": str(member_id), **body.model_dump(mode="json")}),
        )
        stored = await keys.begin(org, request, now=now)
        if stored is not None:
            message_id = UUID(str(stored.body["message_id"]))
            status = await repo.message_status(org, message_id)
            if status is None:
                raise not_found()
            return QueuedMessage.model_validate({"id": message_id, "status": status})
        contact = await repo.holder_contact(org, member_id)
        if contact is None:
            raise not_found()
        person_id, phone = contact
        if phone is None:
            raise invalid("channel", "Aucun numéro de téléphone pour le titulaire.")
        related_type, related_id = "member", member_id
        if body.contribution_id is not None:
            contribution = await repo.contribution(org, body.contribution_id, lock=True)
            if contribution is None or contribution.member_id != member_id:
                raise not_found()
            related_type, related_id = "contribution", contribution.id
            if contribution.status in PAYABLE:
                # Lien joint à la relance : l'envoyeur recalcule le jeton (jamais stocké).
                await self._new_link(repo, org, contribution.id)
        message_id = await repo.queue_message(
            org,
            NewMessage(person_id, body.channel, body.template_code, related_type, related_id, now),
        )
        await keys.complete(org, request, 202, {"message_id": str(message_id)})
        return QueuedMessage(id=message_id, status="en_file")

    # --- Payeur (public, organisation résolue depuis le lien) ------------------------------

    async def _open_link(
        self, repo: PaymentRepository, token: str
    ) -> tuple[UUID, ContributionRecord]:
        target = await repo.resolve_link(token_hash(token))
        if target is None:  # inconnu, expiré ou déjà utilisé (indistinguable : Q-L4-04)
            raise not_found()
        await repo.enter_organization(target.organization_id)
        contribution = await repo.contribution(
            target.organization_id, target.contribution_id, lock=True
        )
        if contribution is None:
            raise not_found()
        if contribution.status not in PAYABLE:
            raise link_gone()
        return target.organization_id, contribution

    async def public_link(self, database: Database, token: str) -> PublicPaymentLink:
        async with database.transaction(None) as session:
            repo = PaymentRepository(session)
            org, contribution = await self._open_link(repo, token)
            given, family = await repo.holder_of_contribution(org, contribution.id)
            return PublicPaymentLink.model_validate(
                {
                    "period_start": contribution.period_start,
                    "amount_xof": contribution.amount_xof,
                    "holder_initials": initials(given, family),
                    "channels": self.config.channels.names(),
                }
            )

    async def checkout(
        self, database: Database, token: str, body: CheckoutRequest, idempotency_key: str
    ) -> Checkout:
        async with database.transaction(None) as session:
            repo = PaymentRepository(session)
            target = await repo.resolve_link(token_hash(token))
            if target is None:
                raise not_found()
            org = target.organization_id
            await repo.enter_organization(org)
            keys = IdempotencyStore(session)
            now = self.clock.now()
            request = KeyRequest(
                SCOPE_CHECKOUT,
                idempotency_key,
                fingerprint({"link": token_hash(token), **body.model_dump(mode="json")}),
            )
            stored = await keys.begin(org, request, now=now)
            if stored is not None:
                return Checkout.model_validate(stored.body)
            _, contribution = await self._open_link(repo, token)
            channel = self.config.channels.get(body.channel)
            if channel is None:
                raise invalid("channel", "Ce moyen de paiement n'est pas disponible.")
            payment_id = uuid.uuid4()
            started = await channel.start_checkout(
                CheckoutOrder(payment_id=payment_id, amount_xof=contribution.amount_xof)
            )
            await repo.insert_payment(
                org,
                NewPayment(
                    id=payment_id,
                    contribution_id=contribution.id,
                    channel=body.channel,
                    provider_reference=started.provider_reference,
                    amount_xof=contribution.amount_xof,
                    payer_kind=LINK_PAYER_KIND,
                    payer_country_code=body.payer_country_code,
                    received_at=now,
                ),
            )
            result = Checkout(
                payment_id=payment_id, status="en_attente", redirect_url=started.redirect_url
            )
            await keys.complete(org, request, 201, result.model_dump(mode="json"))
            log_event(
                logger,
                logging.INFO,
                "payments.checkout_started",
                organization_id=org,
                payment_id=payment_id,
                channel=body.channel,
            )
            return result
