"""Schémas de l'espace adhérent (P1), conformes aux composants ``My*`` de specs/openapi.yaml.

Aucun champ interne : pas de score ni d'alerte de fraude, pas de trace d'évaluation, pas
d'identifiant de règle, pas d'acte ni de référence HealthOS (test de contrat dédié).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.claims.schemas import ClaimStatus, RuleRef
from api.members.schemas import Entitlements
from api.payments.schemas import ContributionStatus, PaymentChannelValue

type Relationship = Literal["titulaire", "conjoint", "enfant", "autre"]
type PayerKind = Literal["adherent", "employeur", "proche"]


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class MyCard(_Out):
    card_id: UUID
    person_id: UUID
    given_name: str
    family_name: str
    relationship: Relationship
    member_number: str
    plan_code: str
    coverage_rate_bp: int = Field(ge=0, le=10000)
    beneficiaries_count: int = Field(ge=1)
    card_status: Literal["active", "bloquee"]
    blocked_until: datetime | None
    qr_payload: str
    qr_generated_at: datetime
    qr_refresh_at: datetime
    entitlements: Entitlements


class MyBeneficiary(_Out):
    person_id: UUID
    given_name: str
    family_name: str
    relationship: Relationship
    valid_from: date
    valid_to: date | None
    card_status: Literal["active", "bloquee", "aucune"]


class MyBeneficiaryList(_Out):
    items: list[MyBeneficiary]


class MyClaim(_Out):
    id: UUID
    claim_number: str
    beneficiary_person_id: UUID
    beneficiary_given_name: str
    provider_name: str
    service_date: date
    requested_at: datetime
    status: ClaimStatus
    total_xof: int = Field(ge=0)
    covered_xof: int = Field(ge=0)
    patient_share_xof: int = Field(ge=0)
    currency: Literal["XOF"] = "XOF"
    rule: RuleRef | None


class PageInfo(_Out):
    next_cursor: str | None


class MyClaimList(_Out):
    items: list[MyClaim]
    page: PageInfo


class TrackingStep(_Out):
    key: Literal["demande_recue", "accordee", "virement", "recu"]
    state: Literal["fait", "en_cours", "a_venir", "refuse", "annule", "sans_objet"]
    at: datetime | None
    rule: RuleRef | None
    reason_code: str | None


class ClaimTracking(_Out):
    claim: MyClaim
    steps: list[TrackingStep] = Field(min_length=4, max_length=4)


class MyContribution(_Out):
    id: UUID
    period_start: date
    due_on: date
    amount_xof: int = Field(ge=0)
    currency: Literal["XOF"] = "XOF"
    status: ContributionStatus
    paid_at: datetime | None
    channel: PaymentChannelValue | None
    payer_kind: PayerKind | None
    payer_country_code: str | None


class MyContributions(_Out):
    items: list[MyContribution]
    next_due: MyContribution | None
