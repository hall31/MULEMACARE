"""Construction des réponses et des événements, sans aucune donnée médicale ni identifiante
dans les événements (specs/events.md : identifiants pseudonymes et numéros seulement)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.engine import RowMapping

from api.claims.errors import not_found
from api.claims.repository import ClaimsRepository
from api.claims.schemas import (
    Authorization,
    ClaimDecisionRecord,
    ClaimDetail,
    ClaimItem,
    ClaimSummary,
    Decision,
    RuleCheck,
    RuleRef,
)
from api.rules.model import Decision as EngineDecision
from api.rules.model import RuleRef as EngineRuleRef

CURRENCY = "XOF"


def _rule(code: object, version: object) -> RuleRef | None:
    return RuleRef(code=str(code), version=int(str(version))) if code is not None else None


def summary(row: RowMapping) -> ClaimSummary:
    score = row["fraud_score"]
    return ClaimSummary(
        id=row["id"],
        claim_number=row["claim_number"],
        member_id=row["member_id"],
        member_display_name=row["member_display_name"],
        provider_id=row["provider_id"],
        provider_name=row["provider_name"],
        service_date=row["service_date"],
        requested_at=row["requested_at"],
        status=row["status"],
        total_xof=row["total_xof"],
        covered_xof=row["covered_xof"],
        fraud_score=float(score) if score is not None else None,
        fraud_flagged=row["fraud_flagged"],
        rule=_rule(row["rule_code"], row["rule_version"]),
    )


def authorization(row: RowMapping | None) -> Authorization | None:
    if row is None:
        return None
    return Authorization(
        id=row["id"],
        authorization_number=row["authorization_number"],
        kind=row["kind"],
        status=row["status"],
        covered_xof=row["covered_xof"],
        rule=RuleRef(code=row["rule_code"], version=row["rule_version"]),
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
    )


async def detail(repo: ClaimsRepository, claim_id: UUID) -> ClaimDetail:
    row = await repo.summary(claim_id)
    if row is None:
        raise not_found("Dossier introuvable.")
    return ClaimDetail(
        claim=summary(row),
        patient_share_xof=row["patient_share_xof"],
        plan_version_id=row["plan_version_id"],
        review_due_at=row["review_due_at"],
        items=[ClaimItem.model_validate(dict(i)) for i in await repo.items(claim_id)],
        decisions=[
            ClaimDecisionRecord(
                sequence=d["sequence"],
                outcome=d["outcome"],
                source=d["source"],
                rule=_rule(d["rule_code"], d["rule_version"]),
                reason_code=d["reason_code"],
                decided_by=d["decided_by"],
                decided_at=d["decided_at"],
            )
            for d in await repo.decisions(claim_id)
        ],
        authorization=authorization(await repo.authorization(claim_id)),
    )


def engine_decision(decision: EngineDecision) -> Decision:
    return Decision(
        outcome=decision.outcome.value,
        rule=RuleRef(code=decision.rule.code, version=decision.rule.version),
        reason_code=decision.reason_code,
        message=decision.message,
        total_xof=decision.total_xof,
        covered_xof=decision.covered_xof,
        patient_share_xof=decision.patient_share_xof,
        plan_version_id=decision.plan_version_id,
        review_due_at=decision.review_due_at,
        checks=[
            RuleCheck(
                rule=RuleRef(code=c.rule.code, version=c.rule.version),
                passed=c.passed,
                message=c.message,
            )
            for c in decision.checks
        ],
    )


# --- Événements (specs/events.md, v1) ---------------------------------------------------------


def claim_requested(claim: RowMapping, lines: Sequence[tuple[str, int, int]]) -> dict[str, Any]:
    return {
        "claim_id": str(claim["id"]),
        "claim_number": claim["claim_number"],
        "member_id": str(claim["member_id"]),
        "beneficiary_id": str(claim["beneficiary_person_id"]),
        "provider_id": str(claim["provider_id"]),
        "identity_check_id": (
            str(claim["identity_check_id"]) if claim["identity_check_id"] else None
        ),
        "channel": claim["channel"],
        "service_date": claim["service_date"].isoformat(),
        "total_xof": int(claim["total_xof"]),
        "currency": CURRENCY,
        "items": [
            {"line_no": n, "act_code": code, "quantity": qty, "amount_xof": amount}
            for n, (code, qty, amount) in enumerate(lines, start=1)
        ],
    }


def claim_decided(  # noqa: PLR0913 — champs du contrat
    claim: RowMapping,
    *,
    sequence: int,
    outcome: str,
    rule: EngineRuleRef | None,
    reason_code: str,
    decided_by: UUID | None,
) -> dict[str, Any]:
    return {
        "claim_id": str(claim["id"]),
        "claim_number": claim["claim_number"],
        "decision_sequence": sequence,
        "outcome": outcome,
        "source": "regle" if rule is not None else "humain",
        "rule": (
            {"rule_id": str(rule.rule_id), "code": rule.code, "version": rule.version}
            if rule is not None
            else None
        ),
        "reason_code": reason_code,
        "decided_by": str(decided_by) if decided_by else None,
        "member_id": str(claim["member_id"]),
        "provider_id": str(claim["provider_id"]),
        "service_date": claim["service_date"].isoformat(),
        "plan_version_id": str(claim["plan_version_id"]),
        "total_xof": int(claim["total_xof"]),
        "covered_xof": int(claim["covered_xof"]),
        "patient_share_xof": int(claim["patient_share_xof"]),
        "currency": CURRENCY,
    }


def iso(moment: datetime) -> str:
    return moment.isoformat()
