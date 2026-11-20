"""Dépôt des adhérents : seul endroit du module ``members`` où l'on écrit du SQL.

Chaque requête filtre explicitement par ``organization_id`` EN PLUS de la RLS forcée du contrat
(défense en profondeur). La session est celle de la transaction de la requête (ou du
traitement), organisation déjà positionnée.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.repositories import Keyset
from api.rules.model import Period, RuleVersion

if TYPE_CHECKING:
    from _typeshed import DataclassInstance


@dataclass(frozen=True, slots=True)
class PersonRecord:
    id: UUID
    given_name: str
    family_name: str
    birth_date: date
    phone_e164: str | None


@dataclass(frozen=True, slots=True)
class MemberRecord:
    id: UUID
    member_number: str
    person: PersonRecord
    plan_id: UUID
    plan_code: str
    employer_id: UUID | None
    status: str
    status_changed_at: datetime
    enrolled_on: date
    waiting_period_ends_on: date
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DependentRecord:
    id: UUID
    person: PersonRecord
    relationship: str
    valid_from: date
    valid_to: date | None


@dataclass(frozen=True, slots=True)
class PlanTerms:
    """Version de produit publiée (champs utiles à L4) ; compatible ``select_in_force``."""

    id: UUID
    version: int
    period: Period
    state: str
    waiting_period_days: int
    monthly_contribution_xof: int
    family_annual_ceiling_xof: int


@dataclass(frozen=True, slots=True)
class NewPerson:
    given_name: str
    family_name: str
    birth_date: date
    phone_e164: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewMember:
    person_id: UUID
    member_number: str
    plan_id: UUID
    employer_id: UUID | None
    status: str
    enrolled_on: date
    waiting_period_ends_on: date
    created_at: datetime


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    member_id: UUID
    from_status: str | None
    to_status: str
    reason_code: str
    actor_user_id: UUID | None
    at: datetime


@dataclass(frozen=True, slots=True)
class NewDependent:
    member_id: UUID
    person_id: UUID
    relationship: str
    valid_from: date
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NewCard:
    id: UUID
    member_id: UUID
    person_id: UUID
    sealed_secret: bytes
    issued_at: datetime


def _params(record: DataclassInstance) -> dict[str, Any]:
    """Paramètres liés d'un enregistrement à insérer (noms = champs du dataclass)."""
    return {f.name: getattr(record, f.name) for f in fields(record)}


@dataclass(frozen=True, slots=True)
class CardRecord:
    id: UUID
    person_id: UUID
    status: str
    issued_at: datetime


_MEMBER_SELECT = (
    "SELECT m.id, m.member_number, p.id, p.given_name, p.family_name, p.birth_date, "
    "p.phone_e164, m.plan_id, pl.code, m.employer_id, m.status, m.status_changed_at, "
    "m.enrolled_on, m.waiting_period_ends_on, m.created_at "
    "FROM members m "
    "JOIN persons p ON p.organization_id = m.organization_id AND p.id = m.person_id "
    "JOIN plans pl ON pl.organization_id = m.organization_id AND pl.id = m.plan_id "
)


def _member(row: Sequence[Any]) -> MemberRecord:
    return MemberRecord(
        id=row[0],
        member_number=row[1],
        person=PersonRecord(row[2], row[3], row[4], row[5], row[6]),
        plan_id=row[7],
        plan_code=row[8],
        employer_id=row[9],
        status=row[10],
        status_changed_at=row[11],
        enrolled_on=row[12],
        waiting_period_ends_on=row[13],
        created_at=row[14],
    )


def _uuid(value: object) -> UUID:
    if not isinstance(value, UUID):
        msg = "identifiant attendu"
        raise TypeError(msg)
    return value


def _date(value: object) -> date:
    if not isinstance(value, date):
        msg = "date attendue"
        raise TypeError(msg)
    return value


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class MemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def _rows(self, query: str, params: dict[str, Any]) -> Sequence[Any]:
        return (await self._session.execute(text(query), params)).all()

    async def _first(self, query: str, params: dict[str, Any]) -> Any:  # noqa: ANN401
        return (await self._session.execute(text(query), params)).first()

    # --- Organisation, produit, règles -----------------------------------------------------

    async def organization_timezone(self, org: UUID) -> str | None:
        row = await self._first("SELECT timezone FROM organizations WHERE id = :org", {"org": org})
        return None if row is None else str(row[0])

    async def plan_id_by_code(self, org: UUID, code: str) -> UUID | None:
        row = await self._first(
            "SELECT id FROM plans WHERE organization_id = :org AND code = :code",
            {"org": org, "code": code},
        )
        return None if row is None else _uuid(row[0])

    async def plan_terms(self, org: UUID, plan_id: UUID) -> list[PlanTerms]:
        rows = await self._rows(
            "SELECT id, version, valid_from, valid_to, state, waiting_period_days, "
            "monthly_contribution_xof, family_annual_ceiling_xof FROM plan_versions "
            "WHERE organization_id = :org AND plan_id = :plan",
            {"org": org, "plan": plan_id},
        )
        return [
            PlanTerms(r[0], r[1], Period(r[2], r[3]), r[4], r[5], int(r[6]), int(r[7]))
            for r in rows
        ]

    async def rule_versions(self, org: UUID, code: str) -> list[RuleVersion]:
        rows = await self._rows(
            "SELECT v.rule_id, r.code, v.version, v.valid_from, v.valid_to, v.state, v.params "
            "FROM rule_versions v JOIN rules r "
            "ON r.organization_id = v.organization_id AND r.id = v.rule_id "
            "WHERE v.organization_id = :org AND r.code = :code",
            {"org": org, "code": code},
        )
        return [RuleVersion(r[0], r[1], r[2], Period(r[3], r[4]), r[5], dict(r[6])) for r in rows]

    async def employer_exists(self, org: UUID, employer_id: UUID) -> bool:
        row = await self._first(
            "SELECT 1 FROM employers WHERE organization_id = :org AND id = :id",
            {"org": org, "id": employer_id},
        )
        return row is not None

    # --- Personnes et adhérents ------------------------------------------------------------

    async def insert_person(self, org: UUID, person: NewPerson) -> UUID:
        row = await self._first(
            "INSERT INTO persons (organization_id, given_name, family_name, birth_date, "
            "phone_e164, created_at) VALUES (:org, :given_name, :family_name, :birth_date, "
            ":phone_e164, :created_at) RETURNING id",
            {"org": org, **_params(person)},
        )
        return _uuid(row[0])

    async def next_member_number(self, org: UUID) -> str:
        """Numéro continu par organisation, sous verrou de transaction (pas de course)."""
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"members:number:{org}"},
        )
        row = await self._first(
            "SELECT coalesce(max(substring(member_number FROM 4)::bigint), 0) FROM members "
            "WHERE organization_id = :org",
            {"org": org},
        )
        return f"MC-{int(row[0]) + 1:08d}"

    async def insert_member(self, org: UUID, member: NewMember) -> UUID:
        row = await self._first(
            "INSERT INTO members (organization_id, person_id, member_number, plan_id, "
            "employer_id, status, status_changed_at, enrolled_on, waiting_period_ends_on, "
            "created_at) VALUES (:org, :person_id, :member_number, :plan_id, :employer_id, "
            ":status, :created_at, :enrolled_on, :waiting_period_ends_on, :created_at) "
            "RETURNING id",
            {"org": org, **_params(member)},
        )
        return _uuid(row[0])

    async def get(self, org: UUID, member_id: UUID, *, lock: bool = False) -> MemberRecord | None:
        suffix = " FOR UPDATE OF m" if lock else ""
        row = await self._first(
            _MEMBER_SELECT + "WHERE m.organization_id = :org AND m.id = :id" + suffix,
            {"org": org, "id": member_id},
        )
        return None if row is None else _member(row)

    async def list_page(
        self,
        org: UUID,
        *,
        status: str | None,
        term: str | None,
        before: Keyset | None,
        limit: int,
    ) -> list[MemberRecord]:
        clauses = ["m.organization_id = :org"]
        params: dict[str, Any] = {"org": org, "limit": limit}
        if status is not None:
            clauses.append("m.status = :status")
            params["status"] = status
        if term is not None:
            clauses.append(
                "(p.given_name ILIKE :like OR p.family_name ILIKE :like "
                "OR (p.given_name || ' ' || p.family_name) ILIKE :like "
                "OR m.member_number ILIKE :like)"
            )
            params["like"] = _like(term)
        if before is not None:
            clauses.append("(m.created_at, m.id) < (:at, :id)")
            params["at"], params["id"] = before.at, before.id
        rows = await self._rows(
            _MEMBER_SELECT
            + "WHERE "
            + " AND ".join(clauses)
            + " ORDER BY m.created_at DESC, m.id DESC LIMIT :limit",
            params,
        )
        return [_member(r) for r in rows]

    async def members_to_review(self, org: UUID) -> list[MemberRecord]:
        """Adhérents en carence ou actifs, verrouillés pour le traitement quotidien."""
        rows = await self._rows(
            _MEMBER_SELECT + "WHERE m.organization_id = :org AND m.status IN ('carence', 'actif') "
            "ORDER BY m.id FOR UPDATE OF m",
            {"org": org},
        )
        return [_member(r) for r in rows]

    async def set_status(self, org: UUID, member_id: UUID, status: str, now: datetime) -> None:
        await self._session.execute(
            text(
                "UPDATE members SET status = :status, status_changed_at = :now "
                "WHERE organization_id = :org AND id = :id"
            ),
            {"status": status, "now": now, "org": org, "id": member_id},
        )

    async def append_history(self, org: UUID, entry: HistoryEntry) -> datetime:
        """Ajoute un changement ; horodatage strictement croissant par adhérent.

        Deux changements dans la même seconde (adhésion puis traitement, même transaction)
        restent ordonnés : la lecture du statut « à une date » n'est jamais ambiguë.
        """
        row = await self._first(
            "INSERT INTO member_status_history (organization_id, member_id, from_status, "
            "to_status, reason_code, actor_user_id, occurred_at) "
            "SELECT :org, :member_id, :from_status, :to_status, :reason_code, :actor_user_id, "
            "greatest(CAST(:at AS timestamptz), (SELECT max(occurred_at) + interval "
            "'1 microsecond' FROM member_status_history WHERE organization_id = :org "
            "AND member_id = :member_id)) RETURNING occurred_at",
            {"org": org, **_params(entry)},
        )
        value = row[0]
        if not isinstance(value, datetime):
            msg = "horodatage attendu"
            raise TypeError(msg)
        return value

    async def status_at(self, org: UUID, member_id: UUID, moment: datetime) -> str | None:
        """Statut en vigueur à un instant (dernier changement strictement antérieur)."""
        row = await self._first(
            "SELECT to_status FROM member_status_history WHERE organization_id = :org "
            "AND member_id = :member AND occurred_at < :moment "
            "ORDER BY occurred_at DESC LIMIT 1",
            {"org": org, "member": member_id, "moment": moment},
        )
        return None if row is None else str(row[0])

    # --- Cotisations (lecture, pour R-01) ----------------------------------------------------

    async def oldest_unpaid_due_on(
        self, org: UUID, member_id: UUID, day_end: datetime
    ) -> date | None:
        """Plus ancienne échéance non réglée à un instant (réglée APRÈS = impayée à l'époque)."""
        row = await self._first(
            "SELECT min(due_on) FROM contributions WHERE organization_id = :org "
            "AND member_id = :member AND status <> 'annulee' AND due_on < :day_end_date "
            "AND (paid_at IS NULL OR paid_at >= :day_end)",
            {
                "org": org,
                "member": member_id,
                "day_end": day_end,
                "day_end_date": day_end.date(),
            },
        )
        return None if row is None or row[0] is None else _date(row[0])

    async def consumed_xof(self, org: UUID, member_id: UUID, start: date, end: date) -> int:
        row = await self._first(
            "SELECT coalesce(sum(covered_xof), 0) FROM claims WHERE organization_id = :org "
            "AND member_id = :member AND status IN ('accordee_auto', 'accordee', 'payee') "
            "AND service_date BETWEEN :start AND :end",
            {"org": org, "member": member_id, "start": start, "end": end},
        )
        return int(row[0])

    # --- Ayants droit -------------------------------------------------------------------------

    async def insert_dependent(self, org: UUID, dependent: NewDependent) -> UUID:
        row = await self._first(
            "INSERT INTO dependents (organization_id, member_id, person_id, relationship, "
            "valid_from, created_at) VALUES (:org, :member_id, :person_id, :relationship, "
            ":valid_from, :created_at) RETURNING id",
            {"org": org, **_params(dependent)},
        )
        return _uuid(row[0])

    async def dependents(self, org: UUID, member_id: UUID) -> list[DependentRecord]:
        rows = await self._rows(
            "SELECT d.id, p.id, p.given_name, p.family_name, p.birth_date, p.phone_e164, "
            "d.relationship, d.valid_from, d.valid_to FROM dependents d "
            "JOIN persons p ON p.organization_id = d.organization_id AND p.id = d.person_id "
            "WHERE d.organization_id = :org AND d.member_id = :member "
            "ORDER BY d.valid_from, d.created_at, d.id",
            {"org": org, "member": member_id},
        )
        return [
            DependentRecord(r[0], PersonRecord(r[1], r[2], r[3], r[4], r[5]), r[6], r[7], r[8])
            for r in rows
        ]

    async def is_beneficiary(self, org: UUID, member_id: UUID, person_id: UUID) -> bool:
        row = await self._first(
            "SELECT 1 FROM members WHERE organization_id = :org AND id = :member "
            "AND person_id = :person UNION ALL "
            "SELECT 1 FROM dependents WHERE organization_id = :org AND member_id = :member "
            "AND person_id = :person AND valid_to IS NULL LIMIT 1",
            {"org": org, "member": member_id, "person": person_id},
        )
        return row is not None

    # --- Cartes ---------------------------------------------------------------------------------

    async def revoke_active_card(self, org: UUID, person_id: UUID, now: datetime) -> UUID | None:
        row = await self._first(
            "UPDATE cards SET status = 'revoquee', revoked_at = :now "
            "WHERE organization_id = :org AND person_id = :person AND status = 'active' "
            "RETURNING id",
            {"org": org, "person": person_id, "now": now},
        )
        return None if row is None else _uuid(row[0])

    async def insert_card(self, org: UUID, card: NewCard) -> None:
        await self._session.execute(
            text(
                "INSERT INTO cards (id, organization_id, member_id, person_id, "
                "qr_secret_ciphertext, status, issued_at) VALUES (:id, :org, :member_id, "
                ":person_id, :sealed_secret, 'active', :issued_at)"
            ),
            {"org": org, **_params(card)},
        )

    async def card(self, org: UUID, card_id: UUID) -> CardRecord | None:
        row = await self._first(
            "SELECT id, person_id, status, issued_at FROM cards "
            "WHERE organization_id = :org AND id = :id",
            {"org": org, "id": card_id},
        )
        return None if row is None else CardRecord(row[0], row[1], row[2], row[3])
