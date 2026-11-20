"""Écriture dans One, sous ``mulema_app`` (RLS forcée) et dans la transaction de l'appelant.

Toute requête filtre aussi explicitement par ``organization_id`` (organisation cible de
l'import, jamais lue dans la source). En import À BLANC, la transaction est passée en
``READ ONLY`` par l'appelant AVANT tout appel : ``DryRunStore`` ne fait que lire, fabrique des
identifiants en mémoire pour les lignes qui seraient créées, et la base refuserait de toute
façon la moindre écriture (défense en profondeur).

Numérotation : mêmes verrous et mêmes suites que les modules adhésions (``MC-NNNNNNNN``) et
prises en charge (``PEC-AA-NNNNN``), pour qu'un import et l'activité de One ne se marchent
jamais dessus.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.legacy_import.spec import Kind
from api.legacy_import.transform import PersonData


class SqlStore:
    """Lectures et écritures réelles (import appliqué)."""

    def __init__(self, session: AsyncSession, organization_id: UUID, source: str) -> None:
        self.session = session
        self.org = organization_id
        self.source = source

    async def _first(self, query: str, params: Mapping[str, object]) -> Any:  # noqa: ANN401
        result = await self.session.execute(text(query), {"org": self.org, **params})
        return result.first()

    async def _id(self, query: str, params: Mapping[str, object]) -> UUID:
        row = await self._first(query, params)
        if row is None or not isinstance(row[0], UUID):
            msg = "identifiant attendu après insertion"
            raise RuntimeError(msg)
        return row[0]

    # --- lectures -------------------------------------------------------------------------

    async def find(self, kind: Kind | str, external_key: str) -> UUID | None:
        row = await self._first(
            "SELECT one_id FROM external_ids WHERE organization_id = :org AND source = :source "
            "AND kind = :kind AND external_key = :key",
            {"source": self.source, "kind": kind, "key": external_key},
        )
        return None if row is None else UUID(str(row[0]))

    async def member_of_person(self, person_id: UUID) -> UUID | None:
        row = await self._first(
            "SELECT id FROM members WHERE organization_id = :org AND person_id = :person",
            {"person": person_id},
        )
        return None if row is None else UUID(str(row[0]))

    async def contribution_exists(self, member_id: UUID, period_start: date) -> bool:
        row = await self._first(
            "SELECT 1 FROM contributions WHERE organization_id = :org AND member_id = :member "
            "AND period_start = :period",
            {"member": member_id, "period": period_start},
        )
        return row is not None

    async def holder_person(self, member_id: UUID) -> UUID:
        return await self._id(
            "SELECT person_id FROM members WHERE organization_id = :org AND id = :member",
            {"member": member_id},
        )

    async def plan_version_at(self, member_id: UUID, day: date) -> UUID | None:
        """Version importée (ou publiée) de la formule de l'adhérent couvrant ``day`` ; unique."""
        result = await self.session.execute(
            text(
                "SELECT v.id FROM plan_versions v JOIN members m "
                "ON m.organization_id = v.organization_id AND m.plan_id = v.plan_id "
                "WHERE v.organization_id = :org AND m.id = :member AND v.valid_from <= :day "
                "AND (v.valid_to IS NULL OR :day <= v.valid_to)"
            ),
            {"org": self.org, "member": member_id, "day": day},
        )
        rows = result.all()
        return UUID(str(rows[0][0])) if len(rows) == 1 else None

    async def waiting_days(self, plan_id: UUID, day: date) -> int | None:
        result = await self.session.execute(
            text(
                "SELECT waiting_period_days FROM plan_versions WHERE organization_id = :org "
                "AND plan_id = :plan AND valid_from <= :day "
                "AND (valid_to IS NULL OR :day <= valid_to)"
            ),
            {"org": self.org, "plan": plan_id, "day": day},
        )
        rows = result.all()
        return int(rows[0][0]) if len(rows) == 1 else None

    # --- écritures ------------------------------------------------------------------------

    async def link(
        self,
        kind: Kind | str,
        key_name: str,
        external_key: str,
        one_id: UUID,
        run_id: UUID,
        import_status: str | None,
        status_map_version: str | None,
    ) -> None:
        await self.session.execute(
            text(
                "INSERT INTO external_ids (organization_id, source, kind, key_name, external_key, "
                "one_id, import_run_id, import_status, status_map_version) VALUES (:org, "
                ":source, :kind, :key_name, :key, :one_id, :run, :status, :map_version)"
            ),
            {
                "org": self.org,
                "source": self.source,
                "kind": kind,
                "key_name": key_name,
                "key": external_key,
                "one_id": one_id,
                "run": run_id,
                "status": import_status,
                "map_version": status_map_version if import_status else None,
            },
        )

    async def insert_plan(self, values: Mapping[str, object]) -> UUID:
        return await self._id(
            "INSERT INTO plans (organization_id, code, name) VALUES (:org, :code, :name) "
            "RETURNING id",
            {"code": values["code"], "name": values["name"]},
        )

    async def plan_code_taken(self, code: str) -> bool:
        row = await self._first(
            "SELECT 1 FROM plans WHERE organization_id = :org AND code = :code", {"code": code}
        )
        return row is not None

    async def insert_plan_version(self, plan_id: UUID, values: Mapping[str, object]) -> UUID:
        # Toujours en BROUILLON : publier une version importée est une décision humaine (R3).
        return await self._id(
            "INSERT INTO plan_versions (organization_id, plan_id, version, valid_from, valid_to, "
            "state, coverage_rate_bp, family_annual_ceiling_xof, waiting_period_days, "
            "monthly_contribution_xof) SELECT :org, :plan, coalesce(max(version), 0) + 1, "
            ":valid_from, :valid_to, 'brouillon', :rate, :ceiling, :waiting, :monthly "
            "FROM plan_versions WHERE organization_id = :org AND plan_id = :plan RETURNING id",
            {
                "plan": plan_id,
                "valid_from": values["valid_from"],
                "valid_to": values["valid_to"],
                "rate": values["coverage_rate_bp"],
                "ceiling": values["family_annual_ceiling_xof"],
                "waiting": values["waiting_period_days"],
                "monthly": values["monthly_contribution_xof"],
            },
        )

    async def insert_coverage(self, plan_version_id: UUID, values: Mapping[str, object]) -> UUID:
        return await self._id(
            "INSERT INTO coverages (organization_id, plan_version_id, category, label, "
            "annual_limit_xof) VALUES (:org, :pv, :category, :label, :limit) RETURNING id",
            {
                "pv": plan_version_id,
                "category": values["category"],
                "label": values["label"],
                "limit": values["annual_limit_xof"],
            },
        )

    async def insert_provider(self, values: Mapping[str, object]) -> UUID:
        return await self._id(
            "INSERT INTO providers (organization_id, name, kind, city, country_code, status) "
            "VALUES (:org, :name, :kind, :city, :country, :status) RETURNING id",
            {
                "name": values["name"],
                "kind": values["kind"],
                "city": values["city"],
                "country": values["country_code"],
                "status": values["status"],
            },
        )

    async def insert_person(self, person: PersonData) -> UUID:
        return await self._id(
            "INSERT INTO persons (organization_id, given_name, family_name, birth_date, "
            "phone_e164) VALUES (:org, :given, :family, :birth, :phone) RETURNING id",
            {
                "given": person.given_name,
                "family": person.family_name,
                "birth": person.birth_date,
                "phone": person.phone_e164,
            },
        )

    async def insert_member(
        self, person_id: UUID, plan_id: UUID, values: Mapping[str, object], waiting_ends: date
    ) -> UUID:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"members:number:{self.org}"},
        )
        # Pas d'historique de statut ni d'événement : l'import n'est pas un changement de
        # statut, et Laravel reste maître des droits jusqu'à la bascule (ADR-001).
        return await self._id(
            "INSERT INTO members (organization_id, person_id, member_number, plan_id, status, "
            "enrolled_on, waiting_period_ends_on) SELECT :org, :person, "
            "'MC-' || lpad((coalesce(max(substring(member_number FROM 4)::bigint), 0) + 1)::text,"
            " 8, '0'), :plan, :status, :enrolled, :waiting FROM members "
            "WHERE organization_id = :org RETURNING id",
            {
                "person": person_id,
                "plan": plan_id,
                "status": values["status"],
                "enrolled": values["enrolled_on"],
                "waiting": waiting_ends,
            },
        )

    async def insert_dependent(
        self, member_id: UUID, person_id: UUID, relationship: str, valid_from: date
    ) -> UUID:
        return await self._id(
            "INSERT INTO dependents (organization_id, member_id, person_id, relationship, "
            "valid_from) VALUES (:org, :member, :person, :relationship, :valid_from) RETURNING id",
            {
                "member": member_id,
                "person": person_id,
                "relationship": relationship,
                "valid_from": valid_from,
            },
        )

    async def enrolled_on(self, member_id: UUID) -> date:
        row = await self._first(
            "SELECT enrolled_on FROM members WHERE organization_id = :org AND id = :member",
            {"member": member_id},
        )
        if row is None or not isinstance(row[0], date):
            msg = "adhérent introuvable"
            raise RuntimeError(msg)
        return row[0]

    async def insert_contribution(self, member_id: UUID, values: Mapping[str, object]) -> UUID:
        paid_on = values["paid_on"]
        assert isinstance(paid_on, date)
        return await self._id(
            "INSERT INTO contributions (organization_id, member_id, period_start, due_on, "
            "amount_xof, status, paid_at) VALUES (:org, :member, :period, :period, :amount, "
            "'payee', :paid_at) RETURNING id",
            {
                "member": member_id,
                "period": values["period_start"],
                "amount": values["amount_xof"],
                # Heure d'origine non reprise (fuseau MySQL inconnu) : jour du paiement, 00:00 UTC.
                "paid_at": datetime.combine(paid_on, time.min, UTC),
            },
        )

    async def insert_claim(
        self,
        member_id: UUID,
        person_id: UUID,
        provider_id: UUID,
        plan_version_id: UUID,
        values: Mapping[str, object],
    ) -> UUID:
        service_date = values["service_date"]
        assert isinstance(service_date, date)
        prefix = f"PEC-{service_date:%y}"
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": f"claims:{self.org}"},
        )
        total, covered = values["total_xof"], values["covered_xof"]
        assert isinstance(total, int)
        assert isinstance(covered, int)
        return await self._id(
            "INSERT INTO claims (organization_id, claim_number, member_id, beneficiary_person_id, "
            "provider_id, channel, service_date, plan_version_id, status, total_xof, covered_xof, "
            "patient_share_xof, requested_at) SELECT :org, :prefix || '-' || lpad((coalesce(max("
            "substring(claim_number FROM :start)::int), 0) + 1)::text, 5, '0'), :member, "
            ":person, :provider, 'console', :service_date, :pv, :status, :total, :covered, "
            ":share, :requested_at FROM claims WHERE organization_id = :org "
            "AND claim_number LIKE :like AND substring(claim_number FROM :start) ~ '^[0-9]+$'",
            {
                "prefix": prefix,
                "start": len(prefix) + 2,
                "like": f"{prefix}-%",
                "member": member_id,
                "person": person_id,
                "provider": provider_id,
                "service_date": service_date,
                "pv": plan_version_id,
                "status": values["status"],
                "total": total,
                "covered": covered,
                "share": total - covered,
                # Date du soin à 00:00 UTC : l'heure de la demande d'origine n'est pas reprise.
                "requested_at": datetime.combine(service_date, time.min, UTC),
            },
        )


class DryRunStore(SqlStore):
    """Import à blanc : lectures réelles, AUCUNE écriture ; les créations restent en mémoire."""

    def __init__(self, session: AsyncSession, organization_id: UUID, source: str) -> None:
        super().__init__(session, organization_id, source)
        self._links: dict[tuple[str, str], UUID] = {}
        self._persons_with_member: set[UUID] = set()
        self._months: set[tuple[UUID, date]] = set()
        self._codes: set[str] = set()
        self._planned: dict[UUID, dict[str, object]] = {}

    async def find(self, kind: Kind | str, external_key: str) -> UUID | None:
        planned = self._links.get((kind, external_key))
        return planned if planned is not None else await super().find(kind, external_key)

    async def link(
        self,
        kind: Kind | str,
        key_name: str,
        external_key: str,
        one_id: UUID,
        run_id: UUID,
        import_status: str | None,
        status_map_version: str | None,
    ) -> None:
        self._links[(kind, external_key)] = one_id

    def _new(self, **facts: object) -> UUID:
        created = uuid4()
        self._planned[created] = facts
        return created

    async def member_of_person(self, person_id: UUID) -> UUID | None:
        if person_id in self._planned:
            return None
        return await super().member_of_person(person_id)

    async def contribution_exists(self, member_id: UUID, period_start: date) -> bool:
        if (member_id, period_start) in self._months:
            return True
        return member_id not in self._planned and await super().contribution_exists(
            member_id, period_start
        )

    async def holder_person(self, member_id: UUID) -> UUID:
        planned = self._planned.get(member_id)
        if planned is not None:
            person = planned["person"]
            assert isinstance(person, UUID)
            return person
        return await super().holder_person(member_id)

    async def plan_version_at(self, member_id: UUID, day: date) -> UUID | None:
        planned = self._planned.get(member_id)
        if planned is None:
            return await super().plan_version_at(member_id, day)
        plan = planned["plan"]
        assert isinstance(plan, UUID)
        return self._version_at(plan, day)

    def _version_at(self, plan_id: UUID, day: date) -> UUID | None:
        found = [
            version
            for version, facts in self._planned.items()
            if facts.get("plan_of_version") == plan_id
            and facts["valid_from"] <= day  # type: ignore[operator]
            and (facts["valid_to"] is None or day <= facts["valid_to"])  # type: ignore[operator]
        ]
        return found[0] if len(found) == 1 else None

    async def waiting_days(self, plan_id: UUID, day: date) -> int | None:
        if plan_id not in self._planned:
            return await super().waiting_days(plan_id, day)
        version = self._version_at(plan_id, day)
        if version is None:
            return None
        days = self._planned[version]["waiting_period_days"]
        assert isinstance(days, int)
        return days

    async def plan_code_taken(self, code: str) -> bool:
        return code in self._codes or await super().plan_code_taken(code)

    async def insert_plan(self, values: Mapping[str, object]) -> UUID:
        self._codes.add(str(values["code"]))
        return self._new()

    async def insert_plan_version(self, plan_id: UUID, values: Mapping[str, object]) -> UUID:
        return self._new(plan_of_version=plan_id, **values)

    async def insert_coverage(self, plan_version_id: UUID, values: Mapping[str, object]) -> UUID:
        return self._new()

    async def insert_provider(self, values: Mapping[str, object]) -> UUID:
        return self._new()

    async def insert_person(self, person: PersonData) -> UUID:
        return self._new()

    async def insert_member(
        self, person_id: UUID, plan_id: UUID, values: Mapping[str, object], waiting_ends: date
    ) -> UUID:
        self._persons_with_member.add(person_id)
        return self._new(person=person_id, plan=plan_id, enrolled_on=values["enrolled_on"])

    async def enrolled_on(self, member_id: UUID) -> date:
        planned = self._planned.get(member_id)
        if planned is None:
            return await super().enrolled_on(member_id)
        enrolled = planned["enrolled_on"]
        assert isinstance(enrolled, date)
        return enrolled

    async def insert_dependent(
        self, member_id: UUID, person_id: UUID, relationship: str, valid_from: date
    ) -> UUID:
        return self._new()

    async def insert_contribution(self, member_id: UUID, values: Mapping[str, object]) -> UUID:
        period = values["period_start"]
        assert isinstance(period, date)
        self._months.add((member_id, period))
        return self._new()

    async def insert_claim(
        self,
        member_id: UUID,
        person_id: UUID,
        provider_id: UUID,
        plan_version_id: UUID,
        values: Mapping[str, object],
    ) -> UUID:
        return self._new()
