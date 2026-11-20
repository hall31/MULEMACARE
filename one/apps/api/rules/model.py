"""Types du moteur de règles : versions (produit, règle), faits d'un dossier, décision.

Tout est immuable. Les montants sont des entiers en francs CFA (XOF), jamais des flottants.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

CURRENCY = "XOF"

# États d'une version applicable à un soin : publiée (soumise et brouillon exclues).
APPLICABLE_STATES = frozenset({"en_vigueur", "cloturee"})


class Outcome(StrEnum):
    """Issue d'une décision du moteur (``claim_decisions.outcome``)."""

    ACCORDEE_AUTO = "accordee_auto"
    EN_REVUE = "en_revue"
    REFUSEE = "refusee"


@dataclass(frozen=True, slots=True)
class Period:
    """Période d'effet, bornes incluses ; ``valid_to`` nul = ouverte."""

    valid_from: date
    valid_to: date | None

    def contains(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


@dataclass(frozen=True, slots=True)
class RuleVersion:
    """Version d'une règle stockée en données (``rules`` + ``rule_versions``)."""

    rule_id: UUID
    code: str
    version: int
    period: Period
    state: str
    params: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class Coverage:
    """Garantie d'une version de produit ; taux nul = taux de la version."""

    category: str
    coverage_rate_bp: int | None


@dataclass(frozen=True, slots=True)
class PlanVersion:
    """Version de produit avec date d'effet (``plan_versions`` + ``coverages``)."""

    id: UUID
    plan_id: UUID
    version: int
    period: Period
    state: str
    coverage_rate_bp: int
    family_annual_ceiling_xof: int
    waiting_period_days: int
    coverages: tuple[Coverage, ...]


@dataclass(frozen=True, slots=True)
class Catalog:
    """Historique des versions d'un produit et des règles ; la date du soin choisit."""

    plan_versions: tuple[PlanVersion, ...]
    rule_versions: tuple[RuleVersion, ...]


@dataclass(frozen=True, slots=True)
class Tariff:
    """Montant conventionné d'un acte sur une période (barème daté, R-04)."""

    amount_xof: int
    period: Period


@dataclass(frozen=True, slots=True)
class ClaimItem:
    """Ligne de soin : acte, catégorie de garantie, quantité et barème daté de l'acte."""

    act_code: str
    coverage_category: str
    quantity: int
    tariffs: tuple[Tariff, ...]


@dataclass(frozen=True, slots=True)
class MemberFacts:
    """Situation de l'adhérent à la date du soin (fournie par L4)."""

    status: str
    enrolled_on: date
    # Jours d'impayé de cotisation à la date du soin (0 = à jour).
    unpaid_days: int


@dataclass(frozen=True, slots=True)
class ProviderFacts:
    """Prestataire : statut et périodes de convention."""

    active: bool
    conventions: tuple[Period, ...]


@dataclass(frozen=True, slots=True)
class ClaimFacts:
    """Entrée complète du moteur. Aucune donnée médicale, aucune donnée identifiante."""

    plan_id: UUID
    service_date: date
    # Instant de l'évaluation : ne sert qu'à dater l'échéance de revue (R-20).
    evaluated_at: datetime
    member: MemberFacts
    provider: ProviderFacts
    items: tuple[ClaimItem, ...]
    # Consommation familiale déjà imputée sur la période du plafond (R-09).
    family_consumed_xof: int
    fraud_score: Decimal | None


@dataclass(frozen=True, slots=True)
class RuleRef:
    """Règle et version appliquées (``rule_id`` + ``rule_version`` en base)."""

    rule_id: UUID
    code: str
    version: int


@dataclass(frozen=True, slots=True)
class RuleCheck:
    """Résultat d'une règle, expliqué en français (trace d'évaluation)."""

    rule: RuleRef
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class Decision:
    """Décision déterministe du moteur ; rejouable à partir de ses versions."""

    outcome: Outcome
    rule: RuleRef
    reason_code: str
    message: str
    total_xof: int
    covered_xof: int
    patient_share_xof: int
    plan_version_id: UUID
    review_due_at: datetime | None
    checks: tuple[RuleCheck, ...]
    currency: str = CURRENCY

    def evaluation_trace(self) -> list[dict[str, object]]:
        """Trace JSON de ``claim_decisions.evaluation_trace`` (sans donnée médicale)."""
        return [
            {
                "rule_id": str(check.rule.rule_id),
                "rule_code": check.rule.code,
                "rule_version": check.rule.version,
                "passed": check.passed,
                "message": check.message,
            }
            for check in self.checks
        ]

    def as_claim_decision(self) -> dict[str, object]:
        """Colonnes d'une ligne ``claim_decisions`` prise par le moteur (écrite par L5)."""
        return {
            "outcome": self.outcome.value,
            "source": "regle",
            "rule_id": self.rule.rule_id,
            "rule_version": self.rule.version,
            "reason_code": self.reason_code,
            "evaluation_trace": self.evaluation_trace(),
        }
