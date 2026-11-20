"""Moteur de règles déterministe (L2) : ``evaluate(faits, catalogue) -> Décision``.

Fonction pure : aucune E/S, aucune horloge, aucun hasard, aucun appel à un LLM. La date du
soin choisit la version de produit et la version de chaque règle (R3) ; même entrée + même
catalogue = même décision.

Ordre (PRD §5) : R-01 droits, R-04 réseau et barème, R-07 carence, R-09 plafond. La première
règle en échec refuse le dossier avec son code stable. Si toutes passent, R-12 accorde
automatiquement, sinon R-20 route vers le médecin-conseil.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from api.rules import params
from api.rules.errors import OverlappingVersionsError
from api.rules.model import (
    Catalog,
    ClaimFacts,
    ClaimItem,
    Decision,
    Outcome,
    PlanVersion,
    RuleCheck,
    RuleRef,
    RuleVersion,
)
from api.rules.versions import select_in_force

_BP_DENOMINATOR = 10_000
DECISION_RULES = ("R-01", "R-04", "R-07", "R-09", "R-12", "R-20")


@dataclass(frozen=True, slots=True)
class _Line:
    act_code: str
    amount_xof: int | None  # None : acte hors barème à la date du soin
    covered_xof: int


def _fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " FCFA"


def _ref(rule: RuleVersion) -> RuleRef:
    return RuleRef(rule_id=rule.rule_id, code=rule.code, version=rule.version)


def _rules_in_force(catalog: Catalog, facts: ClaimFacts) -> dict[str, RuleVersion]:
    return {
        code: select_in_force(
            (r for r in catalog.rule_versions if r.code == code),
            facts.service_date,
            what=f"la règle {code}",
        )
        for code in DECISION_RULES
    }


def _plan_in_force(catalog: Catalog, facts: ClaimFacts) -> PlanVersion:
    return select_in_force(
        (p for p in catalog.plan_versions if p.plan_id == facts.plan_id),
        facts.service_date,
        what="produit",
    )


def _price(item: ClaimItem, facts: ClaimFacts, plan: PlanVersion) -> _Line:
    tariffs = [t for t in item.tariffs if t.period.contains(facts.service_date)]
    if len(tariffs) > 1:
        raise OverlappingVersionsError(
            f"Plusieurs montants de barème pour {item.act_code} au {facts.service_date:%d/%m/%Y}.",
            "Clôturez l'ancien montant du barème avant d'en ajouter un nouveau.",
        )
    if not tariffs:
        return _Line(item.act_code, None, 0)
    amount = tariffs[0].amount_xof * item.quantity
    rate = next(
        (
            c.coverage_rate_bp
            for c in plan.coverages
            if c.category == item.coverage_category and c.coverage_rate_bp is not None
        ),
        plan.coverage_rate_bp,
    )
    # Arrondi à l'entier inférieur, ligne par ligne (claim_items.covered_xof).
    return _Line(item.act_code, amount, amount * rate // _BP_DENOMINATOR)


def _check_rights(rule: RuleVersion, facts: ClaimFacts) -> RuleCheck:
    p = params.rights(rule)
    member = facts.member
    if member.status not in p.open_statuses:
        return RuleCheck(_ref(rule), False, f"Droits non ouverts · statut « {member.status} ».")
    if member.unpaid_days >= p.suspension_after_unpaid_days:
        return RuleCheck(
            _ref(rule),
            False,
            f"Droits suspendus · cotisation impayée depuis {member.unpaid_days} jours.",
        )
    return RuleCheck(_ref(rule), True, "Droits ouverts · cotisation à jour.")


def _check_network(rule: RuleVersion, facts: ClaimFacts, lines: list[_Line]) -> RuleCheck:
    p = params.network(rule)
    provider = facts.provider
    day = facts.service_date
    if not provider.active:
        return RuleCheck(_ref(rule), False, "Prestataire suspendu · hors réseau.")
    if p.convention_required_at_service_date and not any(
        c.contains(day) for c in provider.conventions
    ):
        return RuleCheck(
            _ref(rule), False, f"Prestataire non conventionné au {day:%d/%m/%Y} · hors réseau."
        )
    off_tariff = sorted({line.act_code for line in lines if line.amount_xof is None})
    if off_tariff:
        return RuleCheck(
            _ref(rule),
            False,
            f"Acte(s) hors barème {day.year} : {', '.join(off_tariff)}.",
        )
    return RuleCheck(_ref(rule), True, f"Prestataire conventionné · barème {day.year}.")


def _check_waiting(rule: RuleVersion, facts: ClaimFacts, plan: PlanVersion) -> RuleCheck:
    params.waiting(rule)
    ends_on = facts.member.enrolled_on + timedelta(days=plan.waiting_period_days)
    if facts.service_date < ends_on:
        return RuleCheck(
            _ref(rule),
            False,
            f"Carence de {plan.waiting_period_days} jours en cours jusqu'au {ends_on:%d/%m/%Y}.",
        )
    return RuleCheck(_ref(rule), True, f"Carence de {plan.waiting_period_days} jours écoulée.")


def _check_ceiling(
    rule: RuleVersion, facts: ClaimFacts, plan: PlanVersion, covered: int
) -> RuleCheck:
    params.ceiling(rule)
    remaining = max(plan.family_annual_ceiling_xof - facts.family_consumed_xof, 0)
    if covered > remaining:
        return RuleCheck(
            _ref(rule),
            False,
            f"Plafond familial insuffisant · reste {_fmt(remaining)}, demandé {_fmt(covered)}.",
        )
    return RuleCheck(_ref(rule), True, f"Plafond familial suffisant · reste {_fmt(remaining)}.")


def _check_auto_approval(rule: RuleVersion, facts: ClaimFacts, total: int) -> RuleCheck:
    p = params.auto_approval(rule)
    if total >= p.total_max_exclusive_xof:
        return RuleCheck(
            _ref(rule),
            False,
            f"Total {_fmt(total)} au-delà du seuil d'accord automatique "
            f"({_fmt(p.total_max_exclusive_xof)} exclu).",
        )
    score = facts.fraud_score
    if score is None:
        return RuleCheck(_ref(rule), False, "Score de fraude absent · revue nécessaire.")
    if score >= p.fraud_score_max_exclusive:
        return RuleCheck(
            _ref(rule),
            False,
            f"Score de fraude {score} au-delà du seuil ({p.fraud_score_max_exclusive} exclu).",
        )
    return RuleCheck(
        _ref(rule),
        True,
        "Accord automatique · toutes les conditions de la règle R-12 sont remplies.",
    )


def evaluate(facts: ClaimFacts, catalog: Catalog) -> Decision:
    """Décide un dossier avec les versions en vigueur à la date du soin."""
    plan = _plan_in_force(catalog, facts)
    rules = _rules_in_force(catalog, facts)
    # Échec rapide : toutes les versions applicables doivent être lisibles, même celles
    # que ce dossier n'atteindra pas (une version illisible n'est jamais appliquée à moitié).
    params.rights(rules["R-01"])
    params.network(rules["R-04"])
    params.waiting(rules["R-07"])
    params.ceiling(rules["R-09"])
    params.auto_approval(rules["R-12"])
    delay = params.review(rules["R-20"]).target_delay_minutes

    lines = [_price(item, facts, plan) for item in facts.items]
    total = sum(line.amount_xof or 0 for line in lines)
    covered = sum(line.covered_xof for line in lines)

    gates = (
        _check_rights(rules["R-01"], facts),
        _check_network(rules["R-04"], facts, lines),
        _check_waiting(rules["R-07"], facts, plan),
        _check_ceiling(rules["R-09"], facts, plan, covered),
    )
    failed = next((check for check in gates if not check.passed), None)
    if failed is not None:
        return Decision(
            outcome=Outcome.REFUSEE,
            rule=failed.rule,
            reason_code=failed.rule.code,
            message=f"Refus · {failed.message}",
            total_xof=total,
            covered_xof=0,
            patient_share_xof=total,
            plan_version_id=plan.id,
            review_due_at=None,
            checks=gates,
        )

    auto = _check_auto_approval(rules["R-12"], facts, total)
    checks = (*gates, auto)
    if auto.passed:
        return Decision(
            outcome=Outcome.ACCORDEE_AUTO,
            rule=auto.rule,
            reason_code=auto.rule.code,
            message=auto.message,
            total_xof=total,
            covered_xof=covered,
            patient_share_xof=total - covered,
            plan_version_id=plan.id,
            review_due_at=None,
            checks=checks,
        )

    review_rule = rules["R-20"]
    return Decision(
        outcome=Outcome.EN_REVUE,
        rule=_ref(review_rule),
        reason_code=review_rule.code,
        message=f"Revue du médecin-conseil · {auto.message}",
        total_xof=total,
        covered_xof=covered,
        patient_share_xof=total - covered,
        plan_version_id=plan.id,
        review_due_at=facts.evaluated_at + timedelta(minutes=delay),
        checks=checks,
    )
