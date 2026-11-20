"""Dépôt des cotisations, paiements, liens et messages : seul endroit SQL de ``payments``.

Filtre explicite par ``organization_id`` en plus de la RLS forcée. Les deux résolutions sans
contexte d'organisation passent EXCLUSIVEMENT par les fonctions SECURITY DEFINER du contrat
(``resolve_organization_by_slug``, ``resolve_payment_link``) ; l'organisation trouvée est
ensuite positionnée (``SET LOCAL``) avant toute autre lecture.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class ContributionRecord:
    id: UUID
    member_id: UUID
    period_start: date
    due_on: date
    amount_xof: int
    status: str
    paid_at: datetime | None
    channel: str | None


@dataclass(frozen=True, slots=True)
class PaymentRecord:
    id: UUID
    contribution_id: UUID | None
    channel: str
    provider_reference: str
    amount_xof: int
    status: str
    payer_kind: str
    payer_country_code: str | None


@dataclass(frozen=True, slots=True)
class NewPayment:
    id: UUID
    contribution_id: UUID
    channel: str
    provider_reference: str
    amount_xof: int
    payer_kind: str
    payer_country_code: str | None
    received_at: datetime


@dataclass(frozen=True, slots=True)
class NewMessage:
    person_id: UUID
    channel: str
    template_code: str
    related_type: str
    related_id: UUID
    created_at: datetime


_PAYMENT = (
    "SELECT id, contribution_id, channel, provider_reference, amount_xof, status, "
    "payer_kind, payer_country_code FROM payments WHERE organization_id = :org AND id = :id"
)
_PAYMENT_LOCKED = _PAYMENT + " FOR UPDATE"


@dataclass(frozen=True, slots=True)
class LinkTarget:
    organization_id: UUID
    contribution_id: UUID


def _uuid(value: object) -> UUID:
    if not isinstance(value, UUID):
        msg = "identifiant attendu"
        raise TypeError(msg)
    return value


_CONTRIBUTION_SELECT = (
    "SELECT c.id, c.member_id, c.period_start, c.due_on, c.amount_xof, c.status, c.paid_at, "
    "(SELECT p.channel FROM payments p WHERE p.organization_id = c.organization_id "
    " AND p.contribution_id = c.id AND p.status = 'confirme' "
    " ORDER BY p.confirmed_at DESC LIMIT 1) "
    "FROM contributions c "
)


def _contribution(row: Sequence[Any]) -> ContributionRecord:
    return ContributionRecord(row[0], row[1], row[2], row[3], int(row[4]), row[5], row[6], row[7])


class PaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _first(self, query: str, params: dict[str, Any]) -> Any:  # noqa: ANN401
        return (await self._session.execute(text(query), params)).first()

    # --- Résolution sans contexte (fonctions SECURITY DEFINER du contrat) -------------------

    async def resolve_organization(self, slug: str) -> UUID | None:
        row = await self._first("SELECT resolve_organization_by_slug(:slug)", {"slug": slug})
        return None if row is None or row[0] is None else _uuid(row[0])

    async def resolve_link(self, token_hash: str) -> LinkTarget | None:
        row = await self._first(
            "SELECT organization_id, contribution_id FROM resolve_payment_link(:hash)",
            {"hash": token_hash},
        )
        return None if row is None else LinkTarget(_uuid(row[0]), _uuid(row[1]))

    async def enter_organization(self, organization_id: UUID) -> None:
        """Positionne l'organisation résolue pour la suite de la transaction (RLS)."""
        await self._session.execute(
            select(func.set_config("app.organization_id", str(organization_id), True))
        )

    # --- Cotisations -------------------------------------------------------------------------

    async def contributions_of(self, org: UUID, member_id: UUID) -> list[ContributionRecord]:
        rows = (
            await self._session.execute(
                text(
                    _CONTRIBUTION_SELECT
                    + "WHERE c.organization_id = :org AND c.member_id = :member "
                    "ORDER BY c.period_start DESC, c.id DESC"
                ),
                {"org": org, "member": member_id},
            )
        ).all()
        return [_contribution(r) for r in rows]

    async def contribution(
        self, org: UUID, contribution_id: UUID, *, lock: bool = False
    ) -> ContributionRecord | None:
        suffix = " FOR UPDATE OF c" if lock else ""
        row = await self._first(
            _CONTRIBUTION_SELECT + "WHERE c.organization_id = :org AND c.id = :id" + suffix,
            {"org": org, "id": contribution_id},
        )
        return None if row is None else _contribution(row)

    async def mark_contribution_paid(self, org: UUID, contribution_id: UUID, now: datetime) -> None:
        await self._session.execute(
            text(
                "UPDATE contributions SET status = 'payee', paid_at = :now "
                "WHERE organization_id = :org AND id = :id"
            ),
            {"now": now, "org": org, "id": contribution_id},
        )

    async def issue_month(
        self, org: UUID, period_start: date, period_end: date, now: datetime
    ) -> int:
        """Une échéance par adhérent inscrit au plus tard le dernier jour du mois.

        Montant = cotisation mensuelle de la version de formule en vigueur au 1er du mois ;
        échéance = 1er du mois (Q-L4-01). Rejouable : (adhérent, mois) est unique.
        """
        result = await self._session.execute(
            text(
                "INSERT INTO contributions (organization_id, member_id, period_start, due_on, "
                "amount_xof, status, created_at) "
                "SELECT m.organization_id, m.id, :start, :start, v.monthly_contribution_xof, "
                "'a_payer', :now FROM members m "
                "JOIN plan_versions v ON v.organization_id = m.organization_id "
                " AND v.plan_id = m.plan_id AND v.state IN ('en_vigueur', 'cloturee') "
                " AND v.valid_from <= :start AND (v.valid_to IS NULL OR v.valid_to >= :start) "
                "WHERE m.organization_id = :org AND m.enrolled_on <= :end "
                "ON CONFLICT (organization_id, member_id, period_start) DO NOTHING"
            ),
            {"org": org, "start": period_start, "end": period_end, "now": now},
        )
        return int(getattr(result, "rowcount", 0) or 0)

    # --- Paiements ---------------------------------------------------------------------------

    async def insert_payment(self, org: UUID, payment: NewPayment) -> None:
        await self._session.execute(
            text(
                "INSERT INTO payments (id, organization_id, contribution_id, channel, "
                "provider_reference, amount_xof, status, payer_kind, payer_country_code, "
                "received_at) VALUES (:id, :org, :contribution_id, :channel, "
                ":provider_reference, :amount_xof, 'en_attente', :payer_kind, "
                ":payer_country_code, :received_at)"
            ),
            {"org": org, **asdict(payment)},
        )

    async def payment(
        self, org: UUID, payment_id: UUID, *, lock: bool = False
    ) -> PaymentRecord | None:
        row = await self._first(
            _PAYMENT_LOCKED if lock else _PAYMENT, {"org": org, "id": payment_id}
        )
        if row is None:
            return None
        return PaymentRecord(row[0], row[1], row[2], row[3], int(row[4]), row[5], row[6], row[7])

    async def set_payment_status(
        self, org: UUID, payment_id: UUID, status: str, confirmed_at: datetime | None
    ) -> None:
        await self._session.execute(
            text(
                "UPDATE payments SET status = :status, confirmed_at = :confirmed "
                "WHERE organization_id = :org AND id = :id"
            ),
            {"status": status, "confirmed": confirmed_at, "org": org, "id": payment_id},
        )

    # --- Liens de paiement ---------------------------------------------------------------------

    async def insert_link(
        self, org: UUID, link_id: UUID, contribution_id: UUID, token_hash: str, ttl_seconds: int
    ) -> datetime:
        """Expiration calculée par la base : même horloge que ``resolve_payment_link``."""
        row = await self._first(
            "INSERT INTO payment_links (id, organization_id, contribution_id, token_hash, "
            "expires_at) VALUES (:id, :org, :contribution, :hash, "
            "now() + make_interval(secs => :ttl)) RETURNING expires_at",
            {
                "id": link_id,
                "org": org,
                "contribution": contribution_id,
                "hash": token_hash,
                "ttl": ttl_seconds,
            },
        )
        value = row[0]
        if not isinstance(value, datetime):
            msg = "date d'expiration attendue"
            raise TypeError(msg)
        return value

    async def link(self, org: UUID, link_id: UUID) -> tuple[UUID, datetime] | None:
        row = await self._first(
            "SELECT id, expires_at FROM payment_links WHERE organization_id = :org AND id = :id",
            {"org": org, "id": link_id},
        )
        return None if row is None else (_uuid(row[0]), row[1])

    async def mark_links_used(self, org: UUID, contribution_id: UUID, now: datetime) -> None:
        await self._session.execute(
            text(
                "UPDATE payment_links SET used_at = :now WHERE organization_id = :org "
                "AND contribution_id = :contribution AND used_at IS NULL"
            ),
            {"now": now, "org": org, "contribution": contribution_id},
        )

    # --- Personne titulaire et messages --------------------------------------------------------

    async def holder_of_contribution(self, org: UUID, contribution_id: UUID) -> tuple[str, str]:
        row = await self._first(
            "SELECT p.given_name, p.family_name FROM contributions c "
            "JOIN members m ON m.organization_id = c.organization_id AND m.id = c.member_id "
            "JOIN persons p ON p.organization_id = m.organization_id AND p.id = m.person_id "
            "WHERE c.organization_id = :org AND c.id = :id",
            {"org": org, "id": contribution_id},
        )
        return (str(row[0]), str(row[1])) if row is not None else ("", "")

    async def holder_contact(self, org: UUID, member_id: UUID) -> tuple[UUID, str | None] | None:
        row = await self._first(
            "SELECT p.id, p.phone_e164 FROM members m "
            "JOIN persons p ON p.organization_id = m.organization_id AND p.id = m.person_id "
            "WHERE m.organization_id = :org AND m.id = :id",
            {"org": org, "id": member_id},
        )
        return None if row is None else (_uuid(row[0]), row[1])

    async def queue_message(self, org: UUID, message: NewMessage) -> UUID:
        row = await self._first(
            "INSERT INTO outbound_messages (organization_id, person_id, channel, template_code, "
            "related_type, related_id, status, created_at) VALUES (:org, :person_id, :channel, "
            ":template_code, :related_type, :related_id, 'en_file', :created_at) RETURNING id",
            {"org": org, **asdict(message)},
        )
        return _uuid(row[0])

    async def message_status(self, org: UUID, message_id: UUID) -> str | None:
        row = await self._first(
            "SELECT status FROM outbound_messages WHERE organization_id = :org AND id = :id",
            {"org": org, "id": message_id},
        )
        return None if row is None else str(row[0])
