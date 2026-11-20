"""Pont vers le moteur de règles L2 : L5 fournit les FAITS, L2 décide. Aucune règle ici.

- ``evaluate`` est appelé tel quel (``api.rules.engine.evaluate``) ;
- le prix ligne à ligne (``claim_items.covered_xof``) reprend la fonction de prix du moteur
  (``engine._price``), car ``Decision`` ne donne que des totaux (claims/QUESTIONS.md Q-L5-03) ;
- ID-03 (codes faux) et HL-01 (hors ligne) sont des règles techniques en données que L2 ne lit
  pas : leurs paramètres sont lus ici avec un schéma fermé, et leur version choisie par
  ``api.rules.versions.select_in_force`` (même règle de date que L2).

Faits fournis par L5 (Q-L2-01, Q-L2-06, défauts à valider, QUESTIONS.md Q-L5-04/05) :
statut à la date du soin (historique, sinon statut courant), jours d'impayé à la date du soin,
consommation familiale de l'année civile du soin.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Final
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.claims.errors import ClaimsError
from api.rules import engine, params
from api.rules.errors import RulesError
from api.rules.model import (
    APPLICABLE_STATES,
    Catalog,
    ClaimFacts,
    Decision,
    MemberFacts,
    Period,
    RuleVersion,
)
from api.rules.repository import RulesRepository
from api.rules.versions import select_in_force

CONSUMING_STATUSES: Final = ("accordee_auto", "accordee", "payee")
_RULES_STATUS: Final[Mapping[str, int]] = {"NOT-01": 404, "RUL-02": 409, "VAL-01": 422}


def from_rules_error(exc: RulesError) -> ClaimsError:
    code = exc.code if exc.code in {"NOT-01", "RUL-02", "VAL-01"} else "SYS-01"
    return ClaimsError(
        code,  # type: ignore[arg-type]  # sous-ensemble vérifié ci-dessus
        _RULES_STATUS.get(code, 500),
        exc.message,
        exc.action,
    )


async def driver_connection(session: AsyncSession) -> psycopg.AsyncConnection[Any]:
    """Connexion psycopg de la transaction de la requête (même RLS, même rôle)."""
    connection = await session.connection()
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    if not isinstance(driver, psycopg.AsyncConnection):
        msg = "pilote inattendu : psycopg asynchrone attendu"
        raise TypeError(msg)
    return driver


def day_bounds(day: date, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    start = datetime.combine(day, time.min, zone)
    return start, start + timedelta(days=1)


# --- Règles techniques en données (ID-03, HL-01) -----------------------------------------------


@dataclass(frozen=True, slots=True)
class CodePolicy:
    """ID-03 : nombre de codes faux avant blocage, durée du blocage."""

    rule: RuleVersion
    max_failures: int
    block: timedelta


@dataclass(frozen=True, slots=True)
class OfflineRules:
    """HL-01 (validité) et R-12 (seuil) en vigueur à une date."""

    offline: RuleVersion
    auto: RuleVersion
    validity: timedelta
    threshold_xof: int


def _int_param(rule: RuleVersion, key: str) -> int:
    expected = {
        "ID-03": {"codes_faux_avant_blocage", "duree_blocage_minutes"},
        "HL-01": {"validite_accord_provisoire_minutes"},
    }[rule.code]
    value = rule.params.get(key)
    if set(rule.params) != expected or type(value) is not int or value < 1:
        raise ClaimsError(
            "VAL-01",
            422,
            f"Paramètres invalides pour {rule.code} v{rule.version}.",
            "Corrigez la version de règle (nouvelle version) avant de l'appliquer.",
        )
    return value


async def rule_in_force(
    session: AsyncSession, organization_id: UUID, code: str, at: date
) -> RuleVersion:
    rows = (
        await session.execute(
            text(
                "SELECT v.rule_id, r.code, v.version, v.valid_from, v.valid_to, v.state, v.params "
                "FROM rule_versions v JOIN rules r "
                "ON r.organization_id = v.organization_id AND r.id = v.rule_id "
                "WHERE v.organization_id = :org AND r.code = :code AND v.state = ANY(:states)"
            ),
            {"org": organization_id, "code": code, "states": sorted(APPLICABLE_STATES)},
        )
    ).all()
    versions = [
        RuleVersion(
            rule_id=r[0],
            code=r[1],
            version=r[2],
            period=Period(r[3], r[4]),
            state=r[5],
            params=r[6],
        )
        for r in rows
    ]
    try:
        return select_in_force(versions, at, what=f"la règle {code}")
    except RulesError as exc:
        raise from_rules_error(exc) from exc


async def code_policy(session: AsyncSession, organization_id: UUID, at: date) -> CodePolicy:
    rule = await rule_in_force(session, organization_id, "ID-03", at)
    return CodePolicy(
        rule=rule,
        max_failures=_int_param(rule, "codes_faux_avant_blocage"),
        block=timedelta(minutes=_int_param(rule, "duree_blocage_minutes")),
    )


async def offline_rules(session: AsyncSession, organization_id: UUID, at: date) -> OfflineRules:
    offline = await rule_in_force(session, organization_id, "HL-01", at)
    auto = await rule_in_force(session, organization_id, "R-12", at)
    try:
        threshold = params.auto_approval(auto).total_max_exclusive_xof
    except RulesError as exc:
        raise from_rules_error(exc) from exc
    return OfflineRules(
        offline=offline,
        auto=auto,
        validity=timedelta(minutes=_int_param(offline, "validite_accord_provisoire_minutes")),
        threshold_xof=threshold,
    )


async def review_delay(session: AsyncSession, organization_id: UUID, at: date) -> timedelta:
    rule = await rule_in_force(session, organization_id, "R-20", at)
    try:
        return timedelta(minutes=params.review(rule).target_delay_minutes)
    except RulesError as exc:
        raise from_rules_error(exc) from exc


# --- Faits et évaluation -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClaimContext:
    """Ce que L5 sait du dossier avant l'évaluation."""

    organization_id: UUID
    timezone: str
    member_id: UUID
    plan_id: UUID
    provider_id: UUID
    service_date: date
    lines: Sequence[tuple[str, int]]
    fraud_score: Decimal | None
    evaluated_at: datetime


@dataclass(frozen=True, slots=True)
class PricedLine:
    act_code: str
    quantity: int
    unit_amount_xof: int
    amount_xof: int
    covered_xof: int


@dataclass(frozen=True, slots=True)
class Evaluation:
    decision: Decision
    lines: tuple[PricedLine, ...]


async def _member_facts(session: AsyncSession, c: ClaimContext) -> MemberFacts:
    _, day_end = day_bounds(c.service_date, c.timezone)
    row = (
        await session.execute(
            text(
                "SELECT m.enrolled_on, coalesce(("
                "  SELECT h.to_status FROM member_status_history h "
                "  WHERE h.organization_id = m.organization_id AND h.member_id = m.id "
                "  AND h.occurred_at < :day_end ORDER BY h.occurred_at DESC, h.id DESC LIMIT 1"
                "), m.status), ("
                "  SELECT min(due_on) FROM contributions k "
                "  WHERE k.organization_id = m.organization_id AND k.member_id = m.id "
                "  AND k.status <> 'annulee' AND k.due_on < :day "
                "  AND (k.paid_at IS NULL OR k.paid_at >= :day_end)"
                ") FROM members m WHERE m.organization_id = :org AND m.id = :member"
            ),
            {
                "org": c.organization_id,
                "member": c.member_id,
                "day": c.service_date,
                "day_end": day_end,
            },
        )
    ).one()
    enrolled_on: date = row[0]
    status: str = row[1]
    oldest_unpaid: date | None = row[2]
    unpaid = (c.service_date - oldest_unpaid).days if oldest_unpaid is not None else 0
    return MemberFacts(status=str(status), enrolled_on=enrolled_on, unpaid_days=unpaid)


async def _family_consumed(session: AsyncSession, c: ClaimContext) -> int:
    year = c.service_date.year
    value: int | Decimal = (
        await session.execute(
            text(
                "SELECT coalesce(sum(covered_xof), 0) FROM claims WHERE organization_id = :org "
                "AND member_id = :member AND status = ANY(:statuses) "
                "AND service_date BETWEEN :start AND :end"
            ),
            {
                "org": c.organization_id,
                "member": c.member_id,
                "statuses": list(CONSUMING_STATUSES),
                "start": date(year, 1, 1),
                "end": date(year, 12, 31),
            },
        )
    ).scalar_one()
    return int(value)


async def evaluate_claim(session: AsyncSession, c: ClaimContext) -> Evaluation:
    """Faits → ``engine.evaluate`` (L2). Les erreurs du moteur gardent leur code stable."""
    repository = RulesRepository(await driver_connection(session))
    try:
        catalog: Catalog = await repository.catalog(c.organization_id, c.plan_id)
        items = await repository.claim_items(c.organization_id, list(c.lines))
        provider = await repository.provider_facts(c.organization_id, c.provider_id)
        facts = ClaimFacts(
            plan_id=c.plan_id,
            service_date=c.service_date,
            evaluated_at=c.evaluated_at,
            member=await _member_facts(session, c),
            provider=provider,
            items=tuple(items),
            family_consumed_xof=await _family_consumed(session, c),
            fraud_score=c.fraud_score,
        )
        decision = engine.evaluate(facts, catalog)
        plan = select_in_force(
            (p for p in catalog.plan_versions if p.plan_id == c.plan_id),
            c.service_date,
            what="produit",
        )
        # Prix ligne à ligne : même fonction que le moteur (Q-L5-03).
        priced = [engine._price(item, facts, plan) for item in facts.items]
    except RulesError as exc:
        raise from_rules_error(exc) from exc
    lines = tuple(
        PricedLine(
            act_code=item.act_code,
            quantity=item.quantity,
            unit_amount_xof=(p.amount_xof or 0) // item.quantity,
            amount_xof=p.amount_xof or 0,
            covered_xof=p.covered_xof,
        )
        for item, p in zip(facts.items, priced, strict=True)
    )
    if sum(line.amount_xof for line in lines) != decision.total_xof:
        msg = "prix ligne à ligne incohérent avec le total du moteur"
        raise RuntimeError(msg)
    return Evaluation(decision=decision, lines=lines)
