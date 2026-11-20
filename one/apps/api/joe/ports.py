"""Ports de lecture : le SEUL accès de JOE aux données.

``ReadPorts`` n'expose que des lectures, déléguées aux lectures des autres lots (pas de
réimplémentation des règles) :
- adhérent et droits à une date : ``MemberService.get`` / ``.entitlements`` (L4), vus à travers
  le protocole ``MemberReader`` qui n'en montre que ces deux méthodes ;
- dossiers : ``api.claims.views.detail`` et ``ClaimsRepository.list_summaries`` (L5) ;
- cotisations : ``PaymentRepository.contributions_of`` (L4) ;
- barème, pièces d'un dossier, recherche, journal : ``JoeReadRepository`` (SELECT seulement).
Les outils reçoivent ce port, jamais une session ni un service : aucune méthode d'écriture
n'est atteignable depuis un outil (contrôlé par ``test_guardrails`` et, à l'exécution, par le
garde de lecture seule).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Final, Protocol
from uuid import UUID

from api.claims.errors import ClaimsError
from api.claims.repository import ClaimsRepository
from api.claims.schemas import ClaimDetail, ClaimSummary
from api.claims.views import detail as claim_detail
from api.claims.views import summary as claim_summary
from api.core.clock import Clock
from api.core.context import RequestContext
from api.core.errors import NotFoundError
from api.joe.repository import JoeReadRepository, TariffLine
from api.members.cards import CardKeys
from api.members.errors import MembershipError
from api.members.schemas import Entitlements, Member
from api.members.service import MemberService
from api.payments.repository import ContributionRecord, PaymentRepository

HISTORY_LIMIT: Final = 10
_NOT_FOUND: Final = "NOT-01"


class MemberReader(Protocol):
    """Les deux lectures de L4 dont JOE a besoin, et rien d'autre."""

    async def get(self, member_id: UUID) -> Member: ...

    async def entitlements(self, member_id: UUID, at: date | None) -> Entitlements: ...


type MemberReaderFactory = Callable[[RequestContext], MemberReader]


def member_reader_factory(clock: Clock, card_keys: CardKeys) -> MemberReaderFactory:
    """Lecteur d'adhérents de L4 pour une requête (même horloge et mêmes clés que L4)."""

    def build(ctx: RequestContext) -> MemberReader:
        return MemberService(ctx, clock, card_keys)

    return build


def _not_found(exc: Exception) -> NotFoundError:
    return NotFoundError("Enregistrement introuvable.")


class ReadPorts:
    def __init__(self, ctx: RequestContext, members: MemberReader) -> None:
        self._org = ctx.principal.organization_id
        self._members = members
        self._claims = ClaimsRepository(ctx.session, self._org)
        self._payments = PaymentRepository(ctx.session)
        self._joe = JoeReadRepository(ctx.session, self._org)

    async def member(self, member_id: UUID) -> Member:
        try:
            return await self._members.get(member_id)
        except MembershipError as exc:
            if exc.code == _NOT_FOUND:
                raise _not_found(exc) from exc
            raise

    async def entitlements(self, member_id: UUID, at: date) -> Entitlements:
        try:
            return await self._members.entitlements(member_id, at)
        except MembershipError as exc:
            if exc.code == _NOT_FOUND:
                raise _not_found(exc) from exc
            raise

    async def claim(self, claim_id: UUID) -> ClaimDetail:
        try:
            return await claim_detail(self._claims, claim_id)
        except ClaimsError as exc:
            if exc.code == _NOT_FOUND:
                raise _not_found(exc) from exc
            raise

    async def claim_document_kinds(self, claim_id: UUID) -> tuple[str, ...]:
        return await self._joe.claim_document_kinds(claim_id)

    async def member_claims(self, member_id: UUID) -> Sequence[ClaimSummary]:
        rows = await self._claims.list_summaries(
            providers=None, status=None, fraud_flagged=None, member_id=member_id, start=None,
            end=None, before=None, limit=HISTORY_LIMIT,
        )  # fmt: skip
        return [claim_summary(r) for r in rows]

    async def contributions(self, member_id: UUID) -> list[ContributionRecord]:
        return await self._payments.contributions_of(self._org, member_id)

    async def tariff(self, at: date) -> Sequence[TariffLine]:
        return await self._joe.tariff(at)

    async def member_number(self, member_id: UUID) -> str | None:
        """Numéro d'adhérent (libellé de source), ``None`` si invisible."""
        return await self._joe.member_number(member_id)
