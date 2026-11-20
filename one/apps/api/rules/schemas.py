"""Schémas HTTP des opérations L2, alignés sur ``components.schemas`` de specs/openapi.yaml.

Montants : entiers FCFA (``StrictInt`` : un décimal est refusé, jamais arrondi). Score de fraude :
``Decimal`` (jamais comparé en flottant).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

type AmountXof = Annotated[StrictInt, Field(ge=0)]
type RateBp = Annotated[StrictInt, Field(ge=0, le=10_000)]
type VersionState = Literal["brouillon", "soumise", "en_vigueur", "cloturee"]
type ProviderKind = Literal[
    "clinique", "hopital", "pharmacie", "laboratoire", "imagerie", "cabinet"
]
type CountryCode = Literal["CI", "SN"]
type RuleKind = Literal[
    "droits", "reseau", "carence", "plafond", "accord_automatique", "revue", "identification",
    "hors_ligne",
]  # fmt: skip

CODE_PATTERN = r"^[A-Z0-9-]{2,32}$"
CATEGORY_PATTERN = r"^[a-z_]{2,40}$"
RULE_CODE_PATTERN = r"^[A-Z]{1,3}-[0-9]{2}$"


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class PageInfo(_Out):
    next_cursor: str | None


# --- Produits ----------------------------------------------------------------------------------


class Coverage(_In):
    category: str = Field(pattern=CATEGORY_PATTERN)
    label: str = Field(min_length=1)
    coverage_rate_bp: RateBp | None = None
    annual_limit_xof: AmountXof | None = None
    limit_scope: Literal["famille", "beneficiaire"]


class PlanVersion(_Out):
    id: UUID
    plan_id: UUID
    version: int = Field(ge=1)
    valid_from: date
    valid_to: date | None
    state: VersionState
    coverage_rate_bp: int
    family_annual_ceiling_xof: int
    waiting_period_days: int
    monthly_contribution_xof: int
    currency: Literal["XOF"] = "XOF"
    coverages: list[Coverage]


class Plan(_Out):
    id: UUID
    code: str
    name: str
    status: Literal["active", "retired"]
    current_version_id: UUID | None
    versions: list[PlanVersion]


class PlanList(_Out):
    items: list[Plan]


class CreatePlanRequest(_In):
    code: str = Field(pattern=CODE_PATTERN)
    name: str = Field(min_length=1)


class CreatePlanVersionRequest(_In):
    valid_from: date
    valid_to: date | None = None
    coverage_rate_bp: RateBp
    family_annual_ceiling_xof: AmountXof
    waiting_period_days: Annotated[StrictInt, Field(ge=0)]
    monthly_contribution_xof: AmountXof
    coverages: list[Coverage]


# --- Réseau ------------------------------------------------------------------------------------


class ProviderConvention(_Out):
    id: UUID
    valid_from: date
    valid_to: date | None


class Provider(_Out):
    id: UUID
    name: str
    kind: ProviderKind
    city: str
    country_code: CountryCode
    status: Literal["actif", "suspendu"]
    conventioned: bool
    conventions: list[ProviderConvention]


class ProviderList(_Out):
    items: list[Provider]
    page: PageInfo


class CreateProviderRequest(_In):
    name: str = Field(min_length=1)
    kind: ProviderKind
    city: str = Field(min_length=1)
    country_code: CountryCode


class CreateProviderConventionRequest(_In):
    valid_from: date
    valid_to: date | None = None


# --- Nomenclature et barème --------------------------------------------------------------------


class Act(_Out):
    id: UUID
    code: str
    label: str
    coverage_category: str
    requires_prior_approval: bool


class ActList(_Out):
    items: list[Act]


class CreateActRequest(_In):
    code: str = Field(pattern=CODE_PATTERN)
    label: str = Field(min_length=1, max_length=120)
    coverage_category: str = Field(pattern=CATEGORY_PATTERN)
    requires_prior_approval: bool = False


class TariffItem(_Out):
    act_code: str
    label: str
    amount_xof: int
    currency: Literal["XOF"] = "XOF"
    valid_from: date
    valid_to: date | None
    requires_prior_approval: bool


class TariffList(_Out):
    at: date
    items: list[TariffItem]


class CreateTariffItemRequest(_In):
    amount_xof: AmountXof
    valid_from: date
    valid_to: date | None = None


# --- Règles ------------------------------------------------------------------------------------


class RuleVersion(_Out):
    id: UUID
    rule_code: str
    version: int = Field(ge=1)
    valid_from: date
    valid_to: date | None
    state: VersionState
    params: dict[str, Any]


class RuleVersionList(_Out):
    items: list[RuleVersion]


class Rule(_Out):
    code: str
    label: str
    kind: RuleKind
    current_version: RuleVersion | None


class RuleList(_Out):
    items: list[Rule]


class CreateRuleVersionRequest(_In):
    valid_from: date
    valid_to: date | None = None
    params: dict[str, Any]


# --- Simulation --------------------------------------------------------------------------------


class ClaimItemInput(_In):
    act_code: str = Field(min_length=1)
    quantity: Annotated[StrictInt, Field(ge=1)] = 1


class EvaluateRulesRequest(_In):
    member_id: UUID
    beneficiary_id: UUID
    provider_id: UUID
    service_date: date
    fraud_score: Decimal | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    items: list[ClaimItemInput] = Field(min_length=1)


class RuleRef(_Out):
    code: str
    version: int


class RuleCheck(_Out):
    rule: RuleRef
    passed: bool
    message: str


class Decision(_Out):
    outcome: Literal["accordee_auto", "en_revue", "refusee"]
    rule: RuleRef
    reason_code: str
    message: str
    total_xof: int
    covered_xof: int
    patient_share_xof: int
    currency: Literal["XOF"] = "XOF"
    plan_version_id: UUID
    review_due_at: datetime | None
    checks: list[RuleCheck]
