"""Lecture stricte des paramètres de règle stockés en données (``rule_versions.params``).

Chaque règle a un schéma fermé : clé manquante, clé inconnue ou type faux = ``VAL-01``.
Les montants sont des entiers FCFA ; les scores sont lus en ``Decimal`` (jamais comparés en
flottant).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from api.rules.errors import InvalidRuleParamsError
from api.rules.model import RuleVersion

_SUPPORTED_WAITING_SOURCES = frozenset({"plan_version"})
_SUPPORTED_CEILING_SCOPES = frozenset({"famille"})


@dataclass(frozen=True, slots=True)
class RightsParams:
    """R-01 : droits ouverts."""

    open_statuses: frozenset[str]
    suspension_after_unpaid_days: int


@dataclass(frozen=True, slots=True)
class NetworkParams:
    """R-04 : réseau conventionné et barème de l'année."""

    convention_required_at_service_date: bool


@dataclass(frozen=True, slots=True)
class WaitingParams:
    """R-07 : délai de carence (durée portée par la version de produit)."""

    source: str


@dataclass(frozen=True, slots=True)
class CeilingParams:
    """R-09 : plafond annuel."""

    scope: str


@dataclass(frozen=True, slots=True)
class AutoApprovalParams:
    """R-12 : accord automatique, bornes exclues."""

    total_max_exclusive_xof: int
    fraud_score_max_exclusive: Decimal


@dataclass(frozen=True, slots=True)
class ReviewParams:
    """R-20 : revue par le médecin-conseil."""

    target_delay_minutes: int


def _invalid(rule: RuleVersion, detail: str) -> InvalidRuleParamsError:
    return InvalidRuleParamsError(
        f"Paramètres invalides pour {rule.code} v{rule.version} : {detail}.",
        "Corrigez la version de règle (nouvelle version) avant de l'appliquer.",
    )


def _keys(rule: RuleVersion, expected: set[str]) -> Mapping[str, object]:
    params = rule.params
    missing = expected - params.keys()
    extra = params.keys() - expected
    if missing:
        raise _invalid(rule, f"clé(s) manquante(s) {sorted(missing)}")
    if extra:
        raise _invalid(rule, f"clé(s) inconnue(s) {sorted(extra)}")
    return params


def _int(rule: RuleVersion, params: Mapping[str, object], key: str, minimum: int = 0) -> int:
    value = params[key]
    if type(value) is not int or value < minimum:
        raise _invalid(rule, f"« {key} » doit être un entier ≥ {minimum}")
    return value


def _str(rule: RuleVersion, params: Mapping[str, object], key: str, allowed: frozenset[str]) -> str:
    value = params[key]
    if not isinstance(value, str) or value not in allowed:
        raise _invalid(rule, f"« {key} » doit valoir {sorted(allowed)}")
    return value


def _score(rule: RuleVersion, params: Mapping[str, object], key: str) -> Decimal:
    value = params[key]
    if type(value) not in (int, float, str):
        raise _invalid(rule, f"« {key} » doit être un nombre entre 0 et 1")
    score = Decimal(str(value))
    if not score.is_finite() or not Decimal(0) <= score <= Decimal(1):
        raise _invalid(rule, f"« {key} » doit être un nombre entre 0 et 1")
    return score


def rights(rule: RuleVersion) -> RightsParams:
    p = _keys(rule, {"statuts_ouvrant_droits", "suspension_apres_jours_impayes"})
    statuses = p["statuts_ouvrant_droits"]
    if not isinstance(statuses, list) or not all(isinstance(s, str) for s in statuses):
        raise _invalid(rule, "« statuts_ouvrant_droits » doit être une liste de statuts")
    return RightsParams(
        open_statuses=frozenset(str(s) for s in statuses),
        suspension_after_unpaid_days=_int(rule, p, "suspension_apres_jours_impayes", minimum=1),
    )


def network(rule: RuleVersion) -> NetworkParams:
    p = _keys(rule, {"convention_active_a_la_date_du_soin"})
    value = p["convention_active_a_la_date_du_soin"]
    if not isinstance(value, bool):
        raise _invalid(rule, "« convention_active_a_la_date_du_soin » doit être un booléen")
    return NetworkParams(convention_required_at_service_date=value)


def waiting(rule: RuleVersion) -> WaitingParams:
    p = _keys(rule, {"delai_source"})
    return WaitingParams(source=_str(rule, p, "delai_source", _SUPPORTED_WAITING_SOURCES))


def ceiling(rule: RuleVersion) -> CeilingParams:
    p = _keys(rule, {"perimetre"})
    return CeilingParams(scope=_str(rule, p, "perimetre", _SUPPORTED_CEILING_SCOPES))


def auto_approval(rule: RuleVersion) -> AutoApprovalParams:
    p = _keys(rule, {"total_max_exclu_xof", "score_fraude_max_exclu"})
    return AutoApprovalParams(
        total_max_exclusive_xof=_int(rule, p, "total_max_exclu_xof"),
        fraud_score_max_exclusive=_score(rule, p, "score_fraude_max_exclu"),
    )


def review(rule: RuleVersion) -> ReviewParams:
    p = _keys(rule, {"delai_cible_minutes"})
    return ReviewParams(target_delay_minutes=_int(rule, p, "delai_cible_minutes", minimum=1))
