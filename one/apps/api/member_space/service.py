"""Service de l'espace adhérent (P1) : ma carte, mes bénéficiaires, mes soins, mes cotisations.

Le contrat consulté est celui de l'attribution ``adherent`` du jeton (``ctx.access.member_ids``,
posé par ``require_operation``) : jamais un identifiant reçu du client. Les calculs existants
sont réutilisés tels quels : droits et plafond (``MemberService.entitlements``, L4), QR
dynamique (``current_qr_payload``, L4), lien de paiement (``PaymentService``, L4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy.engine import RowMapping

from api.claims.schemas import RuleRef
from api.core.clock import Clock
from api.core.context import RequestContext
from api.core.errors import NotFoundError, RoleForbiddenError
from api.core.pagination import decode_cursor, encode_cursor
from api.core.repositories import Keyset
from api.member_space.repository import MemberSpaceRepository
from api.member_space.schemas import (
    ClaimTracking,
    MyBeneficiary,
    MyBeneficiaryList,
    MyCard,
    MyClaim,
    MyClaimList,
    MyContribution,
    MyContributions,
    PageInfo,
    TrackingStep,
)
from api.member_space.tracking import DecisionView, tracking_steps
from api.members.cards import WINDOW_SECONDS, CardKeys, current_qr_payload, window_of
from api.members.service import MemberService
from api.payments.schemas import PaymentLink
from api.payments.service import PaymentService

PAYABLE: Final = frozenset({"a_payer", "en_retard"})


def _rule(code: object, version: object) -> RuleRef | None:
    return RuleRef(code=str(code), version=int(str(version))) if code is not None else None


def _claim_out(row: RowMapping) -> MyClaim:
    return MyClaim(
        id=row["id"],
        claim_number=row["claim_number"],
        beneficiary_person_id=row["beneficiary_person_id"],
        beneficiary_given_name=row["beneficiary_given_name"],
        provider_name=row["provider_name"],
        service_date=row["service_date"],
        requested_at=row["requested_at"],
        status=row["status"],
        total_xof=int(row["total_xof"]),
        covered_xof=int(row["covered_xof"]),
        patient_share_xof=int(row["patient_share_xof"]),
        rule=_rule(row["rule_code"], row["rule_version"]),
    )


def _contribution_out(row: RowMapping) -> MyContribution:
    return MyContribution(
        id=row["id"],
        period_start=row["period_start"],
        due_on=row["due_on"],
        amount_xof=int(row["amount_xof"]),
        status=row["status"],
        paid_at=row["paid_at"],
        channel=row["channel"],
        payer_kind=row["payer_kind"],
        payer_country_code=row["payer_country_code"],
    )


def _card_status(blocked_until: datetime | None, now: datetime) -> Literal["active", "bloquee"]:
    return "bloquee" if blocked_until is not None and blocked_until > now else "active"


def _active(row: RowMapping) -> bool:
    """Bénéficiaire couvert : titulaire, ou ayant droit sans date de fin (comme L4)."""
    return row["valid_to"] is None


@dataclass(frozen=True, slots=True)
class MemberSpaceService:
    ctx: RequestContext
    clock: Clock
    card_keys: CardKeys

    @property
    def org(self) -> UUID:
        return self.ctx.principal.organization_id

    def member_id(self) -> UUID:
        """Contrat de l'adhérent connecté : exactement un (``UNIQUE`` de ``user_roles``)."""
        if self.ctx.access is None:  # require_operation la renseigne toujours
            msg = "portée d'accès absente : route montée sans require_operation"
            raise RuntimeError(msg)
        members = self.ctx.access.member_ids
        if len(members) != 1:
            raise RoleForbiddenError
        return next(iter(members))

    @property
    def repo(self) -> MemberSpaceRepository:
        return MemberSpaceRepository(self.ctx.session, self.org, self.member_id())

    # --- Ma carte et mes bénéficiaires ----------------------------------------------------

    async def card(self, person_id: UUID | None) -> MyCard:
        repo = self.repo
        contract = await repo.contract()
        if contract is None:
            raise NotFoundError
        covered = [b for b in await repo.beneficiaries() if _active(b)]
        target = person_id or contract["person_id"]
        found = next((b for b in covered if b["person_id"] == target), None)
        if found is None or found["card_id"] is None:
            raise NotFoundError(
                "Aucune carte active pour cette personne.",
                "Demandez une carte à la mutuelle depuis l'aide de votre espace.",
            )
        now = self.clock.now()
        try:
            qr = await current_qr_payload(
                self.ctx.session, self.card_keys, self.org, found["card_id"], now
            )
        except LookupError as exc:  # carte révoquée entre les deux lectures
            raise NotFoundError from exc
        entitlements = await MemberService(
            ctx=self.ctx, clock=self.clock, card_keys=self.card_keys
        ).entitlements(repo.member, None)
        refresh = datetime.fromtimestamp((window_of(now) + 1) * WINDOW_SECONDS, tz=UTC)
        return MyCard(
            card_id=found["card_id"],
            person_id=found["person_id"],
            given_name=found["given_name"],
            family_name=found["family_name"],
            relationship=found["relationship"],
            member_number=contract["member_number"],
            plan_code=contract["plan_code"],
            coverage_rate_bp=await repo.coverage_rate_bp(entitlements.plan_version_id),
            beneficiaries_count=len(covered),
            card_status=_card_status(found["blocked_until"], now),
            blocked_until=found["blocked_until"],
            qr_payload=qr,
            qr_generated_at=now,
            qr_refresh_at=refresh,
            entitlements=entitlements,
        )

    async def beneficiaries(self) -> MyBeneficiaryList:
        now = self.clock.now()
        return MyBeneficiaryList(
            items=[
                MyBeneficiary(
                    person_id=b["person_id"],
                    given_name=b["given_name"],
                    family_name=b["family_name"],
                    relationship=b["relationship"],
                    valid_from=b["valid_from"],
                    valid_to=b["valid_to"],
                    card_status=(
                        "aucune" if b["card_id"] is None else _card_status(b["blocked_until"], now)
                    ),
                )
                for b in await self.repo.beneficiaries()
            ]
        )

    # --- Mes prises en charge ---------------------------------------------------------------

    async def claims(self, cursor: str | None, limit: int) -> MyClaimList:
        position = decode_cursor(cursor)
        rows = await self.repo.claims_page(
            (position.at, position.id) if position else None, limit + 1
        )
        page = rows[:limit]
        following = Keyset(page[-1]["requested_at"], page[-1]["id"]) if len(rows) > limit else None
        return MyClaimList(
            items=[_claim_out(r) for r in page],
            page=PageInfo(next_cursor=encode_cursor(following)),
        )

    async def tracking(self, claim_id: UUID) -> ClaimTracking:
        repo = self.repo
        row = await repo.claim(claim_id)
        if row is None:
            raise NotFoundError("Dossier introuvable.", "Revenez à la liste de vos soins.")
        decisions = [
            DecisionView(
                outcome=d["outcome"],
                rule_code=d["rule_code"],
                rule_version=d["rule_version"],
                reason_code=d["reason_code"],
                decided_at=d["decided_at"],
            )
            for d in await repo.decisions(claim_id)
        ]
        steps = tracking_steps(row["status"], row["requested_at"], decisions)
        return ClaimTracking(
            claim=_claim_out(row),
            steps=[
                TrackingStep(
                    key=s.key,
                    state=s.state,
                    at=s.at,
                    rule=_rule(s.rule_code, s.rule_version),
                    reason_code=s.reason_code,
                )
                for s in steps
            ],
        )

    # --- Mes cotisations et « inviter un proche à payer » -----------------------------------

    async def contributions(self) -> MyContributions:
        items = [_contribution_out(r) for r in await self.repo.contributions()]
        payable = sorted(
            (c for c in items if c.status in PAYABLE), key=lambda c: (c.due_on, str(c.id))
        )
        return MyContributions(items=items, next_due=payable[0] if payable else None)

    async def invite_payer(
        self, payments: PaymentService, contribution_id: UUID, idempotency_key: str
    ) -> PaymentLink:
        return await payments.create_member_link(
            self.ctx, self.member_id(), contribution_id, idempotency_key
        )
