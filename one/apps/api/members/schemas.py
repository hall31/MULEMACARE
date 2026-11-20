"""Schémas « adhérents », conformes aux composants L4 de specs/openapi.yaml."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

type MemberStatusValue = Literal["actif", "carence", "suspendu"]
type Relationship = Literal["conjoint", "enfant", "autre"]

PHONE_PATTERN = r"^\+[1-9][0-9]{7,14}$"
MEMBER_NUMBER_PATTERN = r"^MC-[0-9]{8}$"


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class PersonInput(_In):
    given_name: str = Field(min_length=1)
    family_name: str = Field(min_length=1)
    birth_date: date
    phone_e164: str | None = Field(default=None, pattern=PHONE_PATTERN)


class CreateMemberRequest(_In):
    holder: PersonInput
    plan_code: str
    employer_id: UUID | None = None
    enrolled_on: date


class AddDependentRequest(_In):
    person: PersonInput
    relationship: Relationship
    valid_from: date


class ChangeMemberStatusRequest(_In):
    to_status: MemberStatusValue


class IssueCardRequest(_In):
    person_id: UUID


class Holder(_Out):
    person_id: UUID
    given_name: str
    family_name: str
    birth_date: date
    phone_e164: str | None


class Dependent(_Out):
    id: UUID
    person_id: UUID
    given_name: str
    family_name: str
    relationship: Relationship
    valid_from: date
    valid_to: date | None


class Member(_Out):
    id: UUID
    member_number: str = Field(pattern=MEMBER_NUMBER_PATTERN)
    holder: Holder
    plan_code: str
    employer_id: UUID | None
    status: MemberStatusValue
    status_changed_at: datetime
    enrolled_on: date
    waiting_period_ends_on: date
    dependents: list[Dependent]


class MemberSummary(_Out):
    id: UUID
    member_number: str
    given_name: str
    family_name: str
    plan_code: str
    status: MemberStatusValue


class PageInfo(_Out):
    next_cursor: str | None


class MemberList(_Out):
    items: list[MemberSummary]
    page: PageInfo


class Entitlements(_Out):
    member_id: UUID
    at: date
    status: MemberStatusValue
    rights_open: bool
    waiting_period_ends_on: date
    plan_version_id: UUID
    family_annual_ceiling_xof: int = Field(ge=0)
    consumed_xof: int = Field(ge=0)
    remaining_xof: int = Field(ge=0)
    currency: Literal["XOF"] = "XOF"


class Card(_Out):
    id: UUID
    person_id: UUID
    status: Literal["active", "revoquee"]
    issued_at: datetime
    revoked_card_id: UUID | None
