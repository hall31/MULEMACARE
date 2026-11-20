"""Service « adhérents » (R2) : adhésion, ayants droit, droits à une date, cartes, statut manuel.

L'organisation vient toujours du principal authentifié (``ctx.principal.organization_id``),
jamais de la requête. Les commandes à ``Idempotency-Key`` réservent leur clé dans la transaction
de la requête et ne stockent que l'identifiant produit (la réponse est relue au rejeu).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final
from uuid import UUID

from fastapi import status

from api.core.clock import Clock
from api.core.context import RequestContext
from api.core.pagination import decode_cursor, encode_cursor
from api.core.repositories import Keyset
from api.core.services import AuditIntent, AuditService
from api.members import cards
from api.members.errors import MembershipError, invalid, not_found
from api.members.idempotency import IdempotencyStore, KeyRequest, StoredResponse, fingerprint
from api.members.repository import (
    DependentRecord,
    MemberRecord,
    MemberRepository,
    NewCard,
    NewDependent,
    NewMember,
    NewPerson,
    PlanTerms,
)
from api.members.schemas import (
    AddDependentRequest,
    Card,
    ChangeMemberStatusRequest,
    CreateMemberRequest,
    Dependent,
    Entitlements,
    Holder,
    IssueCardRequest,
    Member,
    MemberList,
    MemberSummary,
    PageInfo,
    PersonInput,
)
from api.members.status import (
    Change,
    MemberStatus,
    check_manual_change,
    configuration_error,
    end_of_day,
    local_today,
    organization_timezone,
    record_status,
    rights_policy,
    transition,
    unpaid_days,
)
from api.rules.errors import RulesError
from api.rules.versions import select_in_force

SCOPE_CREATE: Final = "command:member.create"
SCOPE_CARD: Final = "command:card.issue"
SCOPE_STATUS: Final = "command:member.status_change"
AUDIT_STATUS_CHANGED: Final = "member.status_changed"


def _new_person(person: PersonInput, now: datetime) -> NewPerson:
    return NewPerson(
        given_name=person.given_name,
        family_name=person.family_name,
        birth_date=person.birth_date,
        phone_e164=person.phone_e164,
        created_at=now,
    )


def plan_in_force(terms: list[PlanTerms], day: date) -> PlanTerms:
    return select_in_force(terms, day, what="la formule")


def _dependent_out(record: DependentRecord) -> Dependent:
    return Dependent.model_validate(
        {
            "id": record.id,
            "person_id": record.person.id,
            "given_name": record.person.given_name,
            "family_name": record.person.family_name,
            "relationship": record.relationship,
            "valid_from": record.valid_from,
            "valid_to": record.valid_to,
        }
    )


def _member_out(record: MemberRecord, dependents: list[DependentRecord]) -> Member:
    return Member.model_validate(
        {
            "id": record.id,
            "member_number": record.member_number,
            "holder": Holder(
                person_id=record.person.id,
                given_name=record.person.given_name,
                family_name=record.person.family_name,
                birth_date=record.person.birth_date,
                phone_e164=record.person.phone_e164,
            ),
            "plan_code": record.plan_code,
            "employer_id": record.employer_id,
            "status": record.status,
            "status_changed_at": record.status_changed_at,
            "enrolled_on": record.enrolled_on,
            "waiting_period_ends_on": record.waiting_period_ends_on,
            "dependents": [_dependent_out(d) for d in dependents],
        }
    )


@dataclass(frozen=True, slots=True)
class MemberService:
    ctx: RequestContext
    clock: Clock
    card_keys: cards.CardKeys

    @property
    def org(self) -> UUID:
        return self.ctx.principal.organization_id

    @property
    def repo(self) -> MemberRepository:
        return MemberRepository(self.ctx.session)

    @property
    def keys(self) -> IdempotencyStore:
        return IdempotencyStore(self.ctx.session)

    async def _member_or_404(self, member_id: UUID, *, lock: bool = False) -> MemberRecord:
        record = await self.repo.get(self.org, member_id, lock=lock)
        if record is None:
            raise not_found()
        return record

    async def get(self, member_id: UUID) -> Member:
        record = await self._member_or_404(member_id)
        return _member_out(record, await self.repo.dependents(self.org, member_id))

    async def list_members(
        self, *, status_filter: str | None, term: str | None, cursor: str | None, limit: int
    ) -> MemberList:
        records = await self.repo.list_page(
            self.org, status=status_filter, term=term, before=decode_cursor(cursor), limit=limit + 1
        )
        page, more = records[:limit], len(records) > limit
        following = Keyset(at=page[-1].created_at, id=page[-1].id) if more and page else None
        return MemberList(
            items=[
                MemberSummary.model_validate(
                    {
                        "id": r.id,
                        "member_number": r.member_number,
                        "given_name": r.person.given_name,
                        "family_name": r.person.family_name,
                        "plan_code": r.plan_code,
                        "status": r.status,
                    }
                )
                for r in page
            ],
            page=PageInfo(next_cursor=encode_cursor(following)),
        )

    async def create(self, body: CreateMemberRequest, idempotency_key: str) -> Member:
        now = self.clock.now()
        request = KeyRequest(
            SCOPE_CREATE, idempotency_key, fingerprint(body.model_dump(mode="json"))
        )
        stored = await self.keys.begin(self.org, request, now=now)
        if stored is not None:
            return await self.get(UUID(str(stored.body["member_id"])))

        repo = self.repo
        plan_id = await repo.plan_id_by_code(self.org, body.plan_code)
        if plan_id is None:
            raise invalid("plan_code", "Formule inconnue dans votre organisation.")
        try:
            terms = plan_in_force(await repo.plan_terms(self.org, plan_id), body.enrolled_on)
        except RulesError as exc:
            raise MembershipError(
                "VAL-01",
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "Aucune version de cette formule n'est en vigueur à la date d'adhésion.",
                "Choisissez une autre date ou publiez une version de la formule.",
                errors=invalid("enrolled_on", exc.message).errors,
            ) from exc
        if body.employer_id is not None and not await repo.employer_exists(
            self.org, body.employer_id
        ):
            raise invalid("employer_id", "Employeur inconnu dans votre organisation.")

        waiting_ends = body.enrolled_on + timedelta(days=terms.waiting_period_days)
        initial: MemberStatus = "carence" if waiting_ends > body.enrolled_on else "actif"
        holder = body.holder
        person_id = await repo.insert_person(self.org, _new_person(holder, now))
        member_id = await repo.insert_member(
            self.org,
            NewMember(
                person_id=person_id,
                member_number=await repo.next_member_number(self.org),
                plan_id=plan_id,
                employer_id=body.employer_id,
                status=initial,
                enrolled_on=body.enrolled_on,
                waiting_period_ends_on=waiting_ends,
                created_at=now,
            ),
        )
        change = Change(initial, "adhesion", now, actor_user_id=self.ctx.principal.user_id)
        await record_status(repo, self.org, member_id, None, change)
        await self.keys.complete(self.org, request, 201, {"member_id": str(member_id)})
        return await self.get(member_id)

    async def add_dependent(self, member_id: UUID, body: AddDependentRequest) -> Dependent:
        member = await self._member_or_404(member_id)
        if body.valid_from < member.enrolled_on:
            raise invalid("valid_from", "La date d'effet précède l'adhésion du titulaire.")
        repo = self.repo
        now = self.clock.now()
        person_id = await repo.insert_person(self.org, _new_person(body.person, now))
        dependent_id = await repo.insert_dependent(
            self.org,
            NewDependent(member_id, person_id, body.relationship, body.valid_from, now),
        )
        created = next(
            d for d in await repo.dependents(self.org, member_id) if d.id == dependent_id
        )
        return _dependent_out(created)

    async def entitlements(self, member_id: UUID, at: date | None) -> Entitlements:
        member = await self._member_or_404(member_id)
        repo = self.repo
        timezone = await organization_timezone(repo, self.org)
        day = at or local_today(self.clock.now(), timezone)
        try:
            terms = plan_in_force(await repo.plan_terms(self.org, member.plan_id), day)
        except RulesError as exc:
            raise configuration_error(exc) from exc
        status_then = await repo.status_at(self.org, member.id, end_of_day(day, timezone))
        status_then = status_then or member.status
        policy = await rights_policy(repo, self.org, day)
        late = await unpaid_days(repo, self.org, member.id, day, timezone)
        rights_open = (
            day >= member.enrolled_on
            and status_then in policy.open_statuses
            and late < policy.suspension_after_unpaid_days
        )
        # Plafond familial sur l'année civile de la date (Q-L0-07 / Q-L4-03).
        consumed = await repo.consumed_xof(
            self.org, member.id, date(day.year, 1, 1), date(day.year, 12, 31)
        )
        ceiling = terms.family_annual_ceiling_xof
        return Entitlements.model_validate(
            {
                "member_id": member.id,
                "at": day,
                "status": status_then,
                "rights_open": rights_open,
                "waiting_period_ends_on": member.waiting_period_ends_on,
                "plan_version_id": terms.id,
                "family_annual_ceiling_xof": ceiling,
                "consumed_xof": consumed,
                "remaining_xof": max(ceiling - consumed, 0),
            }
        )

    async def issue_card(
        self, member_id: UUID, body: IssueCardRequest, idempotency_key: str
    ) -> Card:
        now = self.clock.now()
        request = KeyRequest(
            SCOPE_CARD,
            idempotency_key,
            fingerprint({"member_id": str(member_id), **body.model_dump(mode="json")}),
        )
        stored = await self.keys.begin(self.org, request, now=now)
        if stored is not None:
            return await self._stored_card(stored)
        await self._member_or_404(member_id)
        repo = self.repo
        if not await repo.is_beneficiary(self.org, member_id, body.person_id):
            raise not_found()
        revoked = await repo.revoke_active_card(self.org, body.person_id, now)
        card_id = uuid.uuid4()
        sealed = self.card_keys.seal(cards.new_secret(), organization_id=self.org, card_id=card_id)
        await repo.insert_card(self.org, NewCard(card_id, member_id, body.person_id, sealed, now))
        await self.keys.complete(
            self.org,
            request,
            201,
            {"card_id": str(card_id), "revoked_card_id": None if revoked is None else str(revoked)},
        )
        return Card(
            id=card_id,
            person_id=body.person_id,
            status="active",
            issued_at=now,
            revoked_card_id=revoked,
        )

    async def _stored_card(self, stored: StoredResponse) -> Card:
        record = await self.repo.card(self.org, UUID(str(stored.body["card_id"])))
        if record is None:
            raise not_found()
        revoked = stored.body.get("revoked_card_id")
        return Card.model_validate(
            {
                "id": record.id,
                "person_id": record.person_id,
                "status": record.status,
                "issued_at": record.issued_at,
                "revoked_card_id": None if revoked is None else UUID(str(revoked)),
            }
        )

    async def change_status(
        self, member_id: UUID, body: ChangeMemberStatusRequest, idempotency_key: str
    ) -> Member:
        now = self.clock.now()
        request = KeyRequest(
            SCOPE_STATUS,
            idempotency_key,
            fingerprint({"member_id": str(member_id), **body.model_dump(mode="json")}),
        )
        stored = await self.keys.begin(self.org, request, now=now)
        if stored is not None:
            return await self.get(member_id)
        repo = self.repo
        member = await self._member_or_404(member_id, lock=True)
        await check_manual_change(
            repo, org=self.org, member=member, to_status=body.to_status, now=now
        )
        change = Change(
            body.to_status, "decision_gestionnaire", now, actor_user_id=self.ctx.principal.user_id
        )
        await transition(repo, self.org, member, change)
        await AuditService.for_session(self.ctx.session).record(
            self.ctx,
            AuditIntent(
                AUDIT_STATUS_CHANGED,
                "member",
                member_id,
                {"from_status": member.status, "to_status": body.to_status},
            ),
        )
        await self.keys.complete(self.org, request, 200, {"member_id": str(member_id)})
        return await self.get(member_id)
