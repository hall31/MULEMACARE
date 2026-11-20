"""Services du noyau : règles d'usage entre les routes et les dépôts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.context import RequestContext
from api.core.errors import (
    DuplicateUserError,
    FieldError,
    NotFoundError,
    RoleRevocationUnavailableError,
    ValidationFailedError,
)
from api.core.jsonlog import IDENTIFYING_KEYS
from api.core.pagination import decode_cursor, encode_cursor
from api.core.permissions import NON_GRANTABLE_ROLES, RoleGrant
from api.core.repositories import (
    AuditEntry,
    AuditQuery,
    AuditRecord,
    AuditRepository,
    JsonValue,
    OrganizationRecord,
    OrganizationRepository,
    UserRecord,
    UserRepository,
)
from api.core.schemas import (
    AuditEvent,
    AuditEventList,
    AuditEventsParams,
    CreateUserRequest,
    CurrentUser,
    Organization,
    PageInfo,
    RoleGrantModel,
    User,
    UserList,
)

# Format imposé par la contrainte CHECK de audit_events.action.
_ACTION: Final = re.compile(r"^[a-z_]+(\.[a-z_]+)+$")
_METADATA_KEY: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_UNIQUE_VIOLATION: Final = "23505"

USER_CREATED: Final = "user.created"
USER_ROLES_REPLACED: Final = "user.roles_replaced"


def _clean_metadata(value: object, path: str = "metadata") -> JsonValue:
    """Métadonnées d'audit : identifiants pseudonymes et valeurs techniques seulement."""
    if isinstance(value, dict):
        cleaned: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not _METADATA_KEY.fullmatch(key):
                msg = f"clé de métadonnée invalide dans {path}"
                raise ValueError(msg)
            if key in IDENTIFYING_KEYS:
                msg = f"métadonnée identifiante interdite dans l'audit : {path}.{key}"
                raise ValueError(msg)
            cleaned[key] = _clean_metadata(item, f"{path}.{key}")
        return cleaned
    if isinstance(value, list | tuple):
        return [_clean_metadata(item, path) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, str | int | bool) or value is None:
        return value
    msg = f"type de métadonnée non accepté dans {path}"
    raise ValueError(msg)


def _grant_label(grant: RoleGrant) -> dict[str, str | None]:
    return {
        "role": grant.role.value,
        "provider_id": str(grant.provider_id) if grant.provider_id else None,
        "employer_id": str(grant.employer_id) if grant.employer_id else None,
        "member_id": str(grant.member_id) if grant.member_id else None,
    }


def _user_out(record: UserRecord) -> User:
    return User.model_validate(
        {
            "id": record.id,
            "display_name": record.display_name,
            "email": record.email,
            "status": record.status,
            "roles": [RoleGrantModel.of(g) for g in record.grants],
        }
    )


def _organization_out(record: OrganizationRecord) -> Organization:
    return Organization.model_validate(
        {
            "id": record.id,
            "slug": record.slug,
            "name": record.name,
            "country_code": record.country_code,
            "timezone": record.timezone,
            "currency": record.currency,
            "capabilities": list(record.capabilities),
        }
    )


def organization_out(record: OrganizationRecord) -> Organization:
    """Organisation au format du contrat (utilisé aussi par l'accueil d'organisation, P3)."""
    return _organization_out(record)


def user_out(record: UserRecord) -> User:
    """Utilisateur au format du contrat (utilisé aussi par l'accueil d'organisation, P3)."""
    return _user_out(record)


def _audit_out(record: AuditRecord) -> AuditEvent:
    return AuditEvent(
        id=record.id,
        occurred_at=record.occurred_at,
        actor_user_id=record.actor_user_id,
        actor_role=record.actor_role,
        action=record.action,
        target_type=record.target_type,
        target_id=record.target_id,
        request_id=record.request_id,
    )


@dataclass(frozen=True, slots=True)
class AuditIntent:
    """Ce qu'un service veut tracer. ``actor_role`` : par défaut, les rôles qui autorisent."""

    action: str
    target_type: str
    target_id: UUID | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    actor_role: str | None = None


class AuditService:
    """Écrit dans le journal immuable. Utilisé par tous les lots (``for_session``)."""

    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    @classmethod
    def for_session(cls, session: AsyncSession) -> AuditService:
        return cls(AuditRepository(session))

    async def record(self, ctx: RequestContext, intent: AuditIntent) -> AuditRecord:
        if not _ACTION.fullmatch(intent.action):
            msg = f"action d'audit invalide (attendu « domaine.verbe ») : {intent.action!r}"
            raise ValueError(msg)
        metadata = _clean_metadata(dict(intent.metadata))
        if not isinstance(metadata, dict):  # un dict nettoyé reste un dict
            msg = "métadonnées d'audit : objet attendu"
            raise TypeError(msg)
        roles = ctx.access.roles if ctx.access is not None else ctx.principal.roles
        default_role = ",".join(sorted(r.value for r in roles)) or None
        return await self._repository.append(
            ctx.principal.organization_id,
            AuditEntry(
                action=intent.action,
                target_type=intent.target_type,
                target_id=intent.target_id,
                actor_user_id=ctx.principal.user_id,
                actor_role=intent.actor_role or default_role,
                request_id=ctx.request_id,
                metadata=metadata,
            ),
        )

    async def list_events(self, ctx: RequestContext, params: AuditEventsParams) -> AuditEventList:
        organization = await OrganizationRepository(ctx.session).get(ctx.principal.organization_id)
        if organization is None:
            raise NotFoundError
        # Dates du filtre = jours civils du fuseau de l'organisation, bornes incluses.
        zone = ZoneInfo(organization.timezone)
        start, end = params.start, params.end
        query = AuditQuery(
            action=params.action,
            target_id=params.target_id,
            start=datetime.combine(start, time.min, zone) if start else None,
            end=datetime.combine(end + timedelta(days=1), time.min, zone) if end else None,
        )
        records, following = await self._repository.list_page(
            ctx.principal.organization_id,
            query,
            before=decode_cursor(params.cursor),
            limit=params.limit,
        )
        return AuditEventList(
            items=[_audit_out(r) for r in records],
            page=PageInfo(next_cursor=encode_cursor(following)),
        )


class OrganizationService:
    def __init__(self, repository: OrganizationRepository) -> None:
        self._repository = repository

    async def current(self, ctx: RequestContext) -> Organization:
        record = await self._repository.get(ctx.principal.organization_id)
        if record is None:
            raise NotFoundError
        return _organization_out(record)


class UserService:
    def __init__(
        self,
        users: UserRepository,
        organizations: OrganizationRepository,
        audit: AuditService,
    ) -> None:
        self._users = users
        self._organizations = organizations
        self._audit = audit

    @classmethod
    def for_session(cls, session: AsyncSession) -> UserService:
        return cls(
            UserRepository(session),
            OrganizationRepository(session),
            AuditService.for_session(session),
        )

    async def me(self, ctx: RequestContext) -> CurrentUser:
        record = await self._users.get(ctx.principal.organization_id, ctx.principal.user_id)
        organization = await self._organizations.get(ctx.principal.organization_id)
        if record is None or organization is None:
            raise NotFoundError
        user = _user_out(record)
        return CurrentUser(
            user=user, organization=_organization_out(organization), roles=user.roles
        )

    async def list_users(self, ctx: RequestContext, *, cursor: str | None, limit: int) -> UserList:
        records, following = await self._users.list_page(
            ctx.principal.organization_id, decode_cursor(cursor), limit
        )
        return UserList(
            items=[_user_out(r) for r in records],
            page=PageInfo(next_cursor=encode_cursor(following)),
        )

    async def _validated_grants(
        self, ctx: RequestContext, requested: list[RoleGrantModel]
    ) -> list[RoleGrant]:
        """Dédoublonne et vérifie que les attributs de portée existent DANS l'organisation.

        ``admin_plateforme`` n'est jamais attribuable par l'API (CR-P3-01) : refus VAL-01.
        """
        grants = [r.to_grant() for r in requested]
        reserved = [
            FieldError(f"roles.{i}.role", "Rôle attribué par l'exploitation de la plateforme.")
            for i, g in enumerate(grants)
            if g.role in NON_GRANTABLE_ROLES
        ]
        if reserved:
            raise ValidationFailedError(errors=tuple(reserved))
        found_providers, found_employers = await self._users.existing_scope_targets(
            ctx.principal.organization_id,
            {g.provider_id for g in grants if g.provider_id},
            {g.employer_id for g in grants if g.employer_id},
        )
        found_members = await self._users.existing_members(
            ctx.principal.organization_id, {g.member_id for g in grants if g.member_id}
        )
        errors = (
            [
                FieldError(
                    f"roles.{i}.provider_id", "Établissement inconnu dans votre organisation."
                )
                for i, g in enumerate(grants)
                if g.provider_id is not None and g.provider_id not in found_providers
            ]
            + [
                FieldError(f"roles.{i}.employer_id", "Employeur inconnu dans votre organisation.")
                for i, g in enumerate(grants)
                if g.employer_id is not None and g.employer_id not in found_employers
            ]
            + [
                FieldError(f"roles.{i}.member_id", "Adhérent inconnu dans votre organisation.")
                for i, g in enumerate(grants)
                if g.member_id is not None and g.member_id not in found_members
            ]
        )
        if errors:
            raise ValidationFailedError(errors=tuple(errors))
        return sorted(set(grants), key=RoleGrant.sort_key)

    async def create(self, ctx: RequestContext, request: CreateUserRequest) -> User:
        org = ctx.principal.organization_id
        grants = await self._validated_grants(ctx, request.roles)
        if await self._users.subject_exists(org, request.idp_subject):
            raise DuplicateUserError
        try:
            user_id = await self._users.insert(
                org,
                subject=request.idp_subject,
                display_name=request.display_name,
                email=request.email,
            )
        except IntegrityError as exc:  # course entre deux créations simultanées
            if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
                raise DuplicateUserError from exc
            raise
        await self._users.add_grants(org, user_id, grants, granted_by=ctx.principal.user_id)
        await self._audit.record(
            ctx,
            AuditIntent(
                USER_CREATED, "user", user_id, {"roles": [_grant_label(g) for g in grants]}
            ),
        )
        record = await self._users.get(org, user_id)
        if record is None:  # invisible juste après insertion : incohérence de RLS
            raise NotFoundError
        return _user_out(record)

    async def replace_roles(
        self, ctx: RequestContext, user_id: UUID, requested: list[RoleGrantModel]
    ) -> User:
        org = ctx.principal.organization_id
        current = await self._users.get(org, user_id)
        if current is None:
            raise NotFoundError
        wanted = await self._validated_grants(ctx, requested)
        before = set(current.grants)
        if before - set(wanted):
            # Le rôle applicatif n'a pas DELETE sur user_roles (contrat L0) : CR-L1-02.
            raise RoleRevocationUnavailableError
        added = [g for g in wanted if g not in before]
        if added:
            await self._users.add_grants(org, user_id, added, granted_by=ctx.principal.user_id)
            await self._audit.record(
                ctx,
                AuditIntent(
                    USER_ROLES_REPLACED,
                    "user",
                    user_id,
                    {
                        "roles_before": [_grant_label(g) for g in current.grants],
                        "roles_after": [_grant_label(g) for g in wanted],
                    },
                ),
            )
        record = await self._users.get(org, user_id)
        if record is None:
            raise NotFoundError
        return _user_out(record)
