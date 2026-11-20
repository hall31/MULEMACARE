"""Schémas des espaces assureur, employeur et plateforme (P3, CR-P3-01), conformes au contrat.

Sorties : agrégats seulement (``KValue`` k-anonyme), aucun nom ni identifiant de personne.
Entrées : modèles FERMÉS (``extra="forbid"``) ; l'organisation ne se reçoit jamais du client.
Le gabarit de configuration (``TemplatePayload``) est un document fermé lui aussi : il ne porte
que du paramétrage (plan de comptes, règles, produits, actes, barème), aucune personne.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.core.schemas import EMAIL_PATTERN, Organization, User

type KStatus = Literal["disponible", "masque"]
type MemberStatus = Literal["actif", "carence", "suspendu"]
type CountryCode = Literal["CI", "SN"]
type HostedCapability = Literal["porteur_de_risque", "gestionnaire", "distributeur"]

TEMPLATE_CODE = r"^[a-z0-9][a-z0-9-]{1,39}$"
SLUG = r"^[a-z0-9][a-z0-9-]{1,62}$"
CATEGORY = r"^[a-z_]{2,40}$"
PLAIN_TEXT = r"^[^<>\x00-\x1f\x7f]+$"


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KValue(_Out):
    status: KStatus
    value: int | None
    contributors: int | None


class StatusCount(_Out):
    status: MemberStatus
    count: KValue


class BenefitCategory(_Out):
    category: str
    claims: KValue
    covered_xof: KValue


class ProviderShare(_Out):
    provider_id: UUID
    name: str
    claims: KValue
    covered_xof: KValue


class OtherProviders(_Out):
    claims: KValue
    covered_xof: KValue


class InsurerPortfolio(_Out):
    period_from: date
    period_to: date
    generated_at: datetime
    k_anonymity_threshold: int
    currency: Literal["XOF"]
    members_total: KValue
    members_by_status: list[StatusCount]
    premiums_xof: KValue
    claims_cost_xof: KValue
    loss_ratio_bp: KValue
    benefits_by_category: list[BenefitCategory]
    top_providers: list[ProviderShare]
    other_providers: OtherProviders
    decision_delay_mean_ms: KValue
    automation_rate_bp: KValue


class EmployerGroupConsumption(_Out):
    employer_id: UUID
    name: str
    members_total: KValue
    members_by_status: list[StatusCount]
    claims: KValue
    covered_xof: KValue
    benefits_by_category: list[BenefitCategory]


class EmployerConsumption(_Out):
    period_from: date
    period_to: date
    generated_at: datetime
    k_anonymity_threshold: int
    currency: Literal["XOF"]
    groups: list[EmployerGroupConsumption]


class EmployerContract(_Out):
    employer_id: UUID
    name: str
    contract_start: date
    contract_end: date | None
    days_remaining: int | None
    status: Literal["en_cours", "a_echeance", "echu", "sans_echeance"]
    members_total: KValue


class EmployerContractList(_Out):
    as_of: date
    within_days: int
    items: list[EmployerContract]


# --- Plateforme ------------------------------------------------------------------------------


class FirstManager(_In):
    idp_subject: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=120, pattern=PLAIN_TEXT)
    email: str | None = Field(default=None, pattern=EMAIL_PATTERN)


class TemplateRef(_In):
    code: str = Field(pattern=TEMPLATE_CODE)
    version: int | None = Field(default=None, ge=1)


class CreateOrganizationRequest(_In):
    slug: str = Field(pattern=SLUG)
    name: str = Field(min_length=1, max_length=120, pattern=PLAIN_TEXT)
    country_code: CountryCode
    capabilities: list[HostedCapability] = Field(min_length=1)
    regulator: str | None = Field(default=None, max_length=40, pattern=PLAIN_TEXT)
    first_manager: FirstManager
    template: TemplateRef


class CreateConfigurationTemplateRequest(_In):
    code: str = Field(pattern=TEMPLATE_CODE)
    country_code: CountryCode
    label: str = Field(min_length=1, max_length=120, pattern=PLAIN_TEXT)


class TemplateContents(_Out):
    ledger_accounts: int
    rules: int
    plans: int
    coverages: int
    acts: int
    tariff_items: int


class TemplateVersionRef(_Out):
    code: str
    version: int


class OrganizationOnboarding(_Out):
    organization: Organization
    first_manager: User
    template: TemplateVersionRef
    copied: TemplateContents


class ConfigurationTemplate(_Out):
    id: UUID
    code: str
    version: int
    country_code: CountryCode
    label: str
    created_at: datetime
    contents: TemplateContents


class ConfigurationTemplateList(_Out):
    items: list[ConfigurationTemplate]


# --- Document du gabarit (stocké en jsonb, fermé) ---------------------------------------------

Amount = Annotated[int, Field(ge=0)]


class _Doc(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TemplateAccount(_Doc):
    code: str = Field(pattern=r"^[0-9]{4,8}$")
    label: str = Field(min_length=1)
    account_class: Literal["actif", "passif", "charge", "produit"]


class TemplateRule(_Doc):
    code: str = Field(pattern=r"^[A-Z]{1,3}-[0-9]{2}$")
    label: str = Field(min_length=1)
    kind: Literal[
        "droits",
        "reseau",
        "carence",
        "plafond",
        "accord_automatique",
        "revue",
        "identification",
        "hors_ligne",
    ]
    params: dict[str, Any]


class TemplateCoverage(_Doc):
    category: str = Field(pattern=CATEGORY)
    label: str = Field(min_length=1)
    coverage_rate_bp: Annotated[int, Field(ge=0, le=10_000)] | None
    annual_limit_xof: Amount | None
    limit_scope: Literal["famille", "beneficiaire"]


class TemplatePlan(_Doc):
    code: str = Field(pattern=r"^[A-Z0-9-]{2,32}$")
    name: str = Field(min_length=1)
    coverage_rate_bp: int = Field(ge=0, le=10_000)
    family_annual_ceiling_xof: Amount
    waiting_period_days: int = Field(ge=0)
    monthly_contribution_xof: Amount
    coverages: list[TemplateCoverage]


class TemplateAct(_Doc):
    code: str = Field(pattern=r"^[A-Z0-9-]{2,32}$")
    label: str = Field(min_length=1)
    coverage_category: str = Field(pattern=CATEGORY)
    requires_prior_approval: bool
    tariff_xof: Amount | None


class TemplatePayload(_Doc):
    format_version: Literal[1]
    ledger_accounts: list[TemplateAccount]
    rules: list[TemplateRule]
    plans: list[TemplatePlan]
    acts: list[TemplateAct]

    def contents(self) -> TemplateContents:
        return TemplateContents(
            ledger_accounts=len(self.ledger_accounts),
            rules=len(self.rules),
            plans=len(self.plans),
            coverages=sum(len(p.coverages) for p in self.plans),
            acts=len(self.acts),
            tariff_items=sum(1 for a in self.acts if a.tariff_xof is not None),
        )
