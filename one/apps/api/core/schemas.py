"""Schémas d'entrée et de sortie du noyau, conformes aux composants L1 de specs/openapi.yaml."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.core.permissions import Role, RoleGrant

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RoleGrantModel(_In):
    role: Role
    provider_id: UUID | None = None
    employer_id: UUID | None = None
    member_id: UUID | None = None

    @model_validator(mode="after")
    def _scope_matches_role(self) -> Self:
        if (self.role is Role.CLINIQUE) != (self.provider_id is not None):
            msg = "provider_id est obligatoire pour le rôle clinique, et interdit sinon"
            raise ValueError(msg)
        if (self.role is Role.EMPLOYEUR) != (self.employer_id is not None):
            msg = "employer_id est obligatoire pour le rôle employeur, et interdit sinon"
            raise ValueError(msg)
        if (self.role is Role.ADHERENT) != (self.member_id is not None):
            msg = "member_id est obligatoire pour le rôle adherent, et interdit sinon"
            raise ValueError(msg)
        return self

    def to_grant(self) -> RoleGrant:
        return RoleGrant(self.role, self.provider_id, self.employer_id, self.member_id)

    @classmethod
    def of(cls, grant: RoleGrant) -> RoleGrantModel:
        return cls(
            role=grant.role,
            provider_id=grant.provider_id,
            employer_id=grant.employer_id,
            member_id=grant.member_id,
        )


class PageInfo(_Out):
    next_cursor: str | None


class Organization(_Out):
    id: UUID
    slug: str
    name: str
    country_code: Literal["CI", "SN"]
    timezone: Literal["Africa/Abidjan", "Africa/Dakar"]
    currency: Literal["XOF"]
    capabilities: list[Literal["porteur_de_risque", "gestionnaire", "distributeur", "plateforme"]]


class User(_Out):
    id: UUID
    display_name: str
    email: str | None
    status: Literal["active", "disabled"]
    roles: list[RoleGrantModel]


class CurrentUser(_Out):
    user: User
    organization: Organization
    roles: list[RoleGrantModel]


class UserList(_Out):
    items: list[User]
    page: PageInfo


class CreateUserRequest(_In):
    idp_subject: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN)
    roles: list[RoleGrantModel] = Field(min_length=1)


class ReplaceUserRolesRequest(_In):
    roles: list[RoleGrantModel]


class AuditEvent(_Out):
    id: UUID
    occurred_at: datetime
    actor_user_id: UUID | None
    actor_role: str | None
    action: str
    target_type: str
    target_id: UUID | None
    request_id: str | None


class AuditEventList(_Out):
    items: list[AuditEvent]
    page: PageInfo


class AuditEventsParams(BaseModel):
    """Paramètres de ``listAuditEvents`` (query) ; ``from`` et ``to`` sont des jours inclus."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    action: str | None = None
    target_id: UUID | None = None
    start: date | None = Field(default=None, alias="from")
    end: date | None = Field(default=None, alias="to")
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
