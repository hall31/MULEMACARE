"""Dépôts du noyau : seul endroit où l'on écrit du SQL.

Chaque requête filtre explicitement par ``organization_id`` EN PLUS de la RLS du contrat
(défense en profondeur : une erreur de politique ne suffit pas à ouvrir une fuite).
Le dépôt d'audit n'expose que ``append`` et ``list_page`` : aucune modification possible.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, Select, and_, func, insert, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.errors import NotAuthenticatedError
from api.core.identity import Identity
from api.core.permissions import Principal, Role, RoleGrant
from api.core.tables import (
    audit_events,
    employers,
    members,
    organizations,
    providers,
    user_roles,
    users,
)


@dataclass(frozen=True, slots=True)
class Keyset:
    """Position de pagination : (horodatage, identifiant)."""

    at: datetime
    id: UUID


@dataclass(frozen=True, slots=True)
class OrganizationRecord:
    id: UUID
    slug: str
    name: str
    country_code: str
    timezone: str
    currency: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: UUID
    display_name: str
    email: str | None
    status: str
    created_at: datetime
    grants: tuple[RoleGrant, ...]


type JsonValue = str | int | bool | list[JsonValue] | dict[str, JsonValue] | None


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Entrée à ajouter au journal (métadonnées déjà nettoyées par le service)."""

    action: str
    target_type: str
    target_id: UUID | None
    actor_user_id: UUID | None
    actor_role: str | None
    request_id: str | None
    metadata: dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class AuditQuery:
    """Filtres de consultation ; ``start`` inclus, ``end`` exclu (UTC)."""

    action: str | None = None
    target_id: UUID | None = None
    start: datetime | None = None
    end: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    actor_role: str | None
    action: str
    target_type: str
    target_id: UUID | None
    request_id: str | None


async def _grants_for(
    session: AsyncSession, organization_id: UUID, user_ids: Sequence[UUID]
) -> dict[UUID, tuple[RoleGrant, ...]]:
    if not user_ids:
        return {}
    rows = await session.execute(
        select(
            user_roles.c.user_id,
            user_roles.c.role,
            user_roles.c.provider_id,
            user_roles.c.employer_id,
            user_roles.c.member_id,
        ).where(
            user_roles.c.organization_id == organization_id,
            user_roles.c.user_id.in_(list(user_ids)),
        )
    )
    grouped: dict[UUID, list[RoleGrant]] = {uid: [] for uid in user_ids}
    for row in rows:
        grouped[row.user_id].append(
            RoleGrant(Role(row.role), row.provider_id, row.employer_id, row.member_id)
        )
    return {uid: tuple(sorted(g, key=RoleGrant.sort_key)) for uid, g in grouped.items()}


class PrincipalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, identity: Identity) -> Principal:
        """Utilisateur actif du sujet, dans l'organisation du jeton ; sinon AUTH-01."""
        row = (
            await self._session.execute(
                select(users.c.id, users.c.status, organizations.c.status.label("org_status"))
                .join(organizations, organizations.c.id == users.c.organization_id)
                .where(
                    users.c.organization_id == identity.organization_id,
                    users.c.idp_subject == identity.subject,
                )
            )
        ).one_or_none()
        if row is None or row.status != "active" or row.org_status == "inactive":
            raise NotAuthenticatedError
        grants = await _grants_for(self._session, identity.organization_id, [row.id])
        return Principal(
            user_id=row.id, organization_id=identity.organization_id, grants=grants[row.id]
        )


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, organization_id: UUID) -> OrganizationRecord | None:
        row = (
            await self._session.execute(
                select(organizations).where(organizations.c.id == organization_id)
            )
        ).one_or_none()
        if row is None:
            return None
        return OrganizationRecord(
            id=row.id,
            slug=row.slug,
            name=row.name,
            country_code=row.country_code,
            timezone=row.timezone,
            currency=row.currency,
            capabilities=tuple(row.capabilities),
        )


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _select(self, organization_id: UUID) -> Select[Any]:
        return select(
            users.c.id, users.c.display_name, users.c.email, users.c.status, users.c.created_at
        ).where(users.c.organization_id == organization_id)

    async def _records(self, organization_id: UUID, rows: Sequence[Row[Any]]) -> list[UserRecord]:
        grants = await _grants_for(self._session, organization_id, [r.id for r in rows])
        return [
            UserRecord(
                id=r.id,
                display_name=r.display_name,
                email=r.email,
                status=r.status,
                created_at=r.created_at,
                grants=grants[r.id],
            )
            for r in rows
        ]

    async def get(self, organization_id: UUID, user_id: UUID) -> UserRecord | None:
        rows = (
            await self._session.execute(self._select(organization_id).where(users.c.id == user_id))
        ).all()
        records = await self._records(organization_id, rows)
        return records[0] if records else None

    async def list_page(
        self, organization_id: UUID, after: Keyset | None, limit: int
    ) -> tuple[list[UserRecord], Keyset | None]:
        query = self._select(organization_id)
        if after is not None:
            query = query.where(tuple_(users.c.created_at, users.c.id) > (after.at, after.id))
        rows = (
            await self._session.execute(
                query.order_by(users.c.created_at, users.c.id).limit(limit + 1)
            )
        ).all()
        records = await self._records(organization_id, rows[:limit])
        following = Keyset(records[-1].created_at, records[-1].id) if len(rows) > limit else None
        return records, following

    async def subject_exists(self, organization_id: UUID, subject: str) -> bool:
        found = await self._session.scalar(
            select(func.count())
            .select_from(users)
            .where(users.c.organization_id == organization_id, users.c.idp_subject == subject)
        )
        return bool(found)

    async def insert(
        self, organization_id: UUID, *, subject: str, display_name: str, email: str | None
    ) -> UUID:
        user_id: UUID | None = await self._session.scalar(
            insert(users)
            .values(
                organization_id=organization_id,
                idp_subject=subject,
                display_name=display_name,
                email=email,
            )
            .returning(users.c.id)
        )
        if user_id is None:  # impossible pour un INSERT … RETURNING réussi
            msg = "INSERT users sans identifiant renvoyé"
            raise RuntimeError(msg)
        return user_id

    async def add_grants(
        self,
        organization_id: UUID,
        user_id: UUID,
        grants: Sequence[RoleGrant],
        *,
        granted_by: UUID,
    ) -> None:
        if not grants:
            return
        await self._session.execute(
            insert(user_roles),
            [
                {
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "role": g.role.value,
                    "provider_id": g.provider_id,
                    "employer_id": g.employer_id,
                    "member_id": g.member_id,
                    "granted_by": granted_by,
                }
                for g in grants
            ],
        )

    async def existing_scope_targets(
        self, organization_id: UUID, provider_ids: set[UUID], employer_ids: set[UUID]
    ) -> tuple[set[UUID], set[UUID]]:
        """Établissements et employeurs qui existent DANS l'organisation."""
        found_providers: set[UUID] = set()
        found_employers: set[UUID] = set()
        if provider_ids:
            found_providers = set(
                (
                    await self._session.scalars(
                        select(providers.c.id).where(
                            providers.c.organization_id == organization_id,
                            providers.c.id.in_(provider_ids),
                        )
                    )
                ).all()
            )
        if employer_ids:
            found_employers = set(
                (
                    await self._session.scalars(
                        select(employers.c.id).where(
                            employers.c.organization_id == organization_id,
                            employers.c.id.in_(employer_ids),
                        )
                    )
                ).all()
            )
        return found_providers, found_employers

    async def existing_members(self, organization_id: UUID, member_ids: set[UUID]) -> set[UUID]:
        """Contrats (adhérents) qui existent DANS l'organisation (portée du rôle adherent)."""
        if not member_ids:
            return set()
        return set(
            (
                await self._session.scalars(
                    select(members.c.id).where(
                        members.c.organization_id == organization_id,
                        members.c.id.in_(member_ids),
                    )
                )
            ).all()
        )


class AuditRepository:
    """Journal d'audit en ajout seul : pas de méthode de modification ni de suppression."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, organization_id: UUID, entry: AuditEntry) -> AuditRecord:
        row = (
            await self._session.execute(
                insert(audit_events)
                .values(
                    organization_id=organization_id,
                    actor_user_id=entry.actor_user_id,
                    actor_role=entry.actor_role,
                    action=entry.action,
                    target_type=entry.target_type,
                    target_id=entry.target_id,
                    request_id=entry.request_id,
                    metadata=entry.metadata,
                )
                .returning(*_AUDIT_COLUMNS)
            )
        ).one()
        return _audit_record(row)

    async def list_page(
        self, organization_id: UUID, query: AuditQuery, *, before: Keyset | None, limit: int
    ) -> tuple[list[AuditRecord], Keyset | None]:
        conditions = [audit_events.c.organization_id == organization_id]
        if query.action is not None:
            conditions.append(audit_events.c.action == query.action)
        if query.target_id is not None:
            conditions.append(audit_events.c.target_id == query.target_id)
        if query.start is not None:
            conditions.append(audit_events.c.occurred_at >= query.start)
        if query.end is not None:
            conditions.append(audit_events.c.occurred_at < query.end)
        if before is not None:
            conditions.append(
                or_(
                    audit_events.c.occurred_at < before.at,
                    and_(audit_events.c.occurred_at == before.at, audit_events.c.id < before.id),
                )
            )
        rows = (
            await self._session.execute(
                select(*_AUDIT_COLUMNS)
                .where(*conditions)
                .order_by(audit_events.c.occurred_at.desc(), audit_events.c.id.desc())
                .limit(limit + 1)
            )
        ).all()
        records = [_audit_record(r) for r in rows[:limit]]
        following = Keyset(records[-1].occurred_at, records[-1].id) if len(rows) > limit else None
        return records, following


_AUDIT_COLUMNS = (
    audit_events.c.id,
    audit_events.c.occurred_at,
    audit_events.c.actor_user_id,
    audit_events.c.actor_role,
    audit_events.c.action,
    audit_events.c.target_type,
    audit_events.c.target_id,
    audit_events.c.request_id,
)


def _audit_record(row: Row[Any]) -> AuditRecord:
    return AuditRecord(
        id=row.id,
        occurred_at=row.occurred_at,
        actor_user_id=row.actor_user_id,
        actor_role=row.actor_role,
        action=row.action,
        target_type=row.target_type,
        target_id=row.target_id,
        request_id=row.request_id,
    )
