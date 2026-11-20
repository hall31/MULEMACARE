"""Propriétés du moteur (hypothesis) : même entrée + même version = même décision (R3)."""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from api.rules.engine import evaluate
from api.rules.model import ClaimFacts, ClaimItem, MemberFacts, Outcome, Period, ProviderFacts
from api.rules.tests.builders import CATALOG, PLAN_ID, TARIFFS

ACT_CODES = [*TARIFFS, "ACTE-INCONNU"]
DECIDING_CODES = {"R-01", "R-04", "R-07", "R-09", "R-12", "R-20"}

service_dates = st.dates(min_value=date(2025, 1, 1), max_value=date(2026, 12, 31))

items = st.builds(
    ClaimItem,
    act_code=st.sampled_from(ACT_CODES),
    coverage_category=st.sampled_from(["soins_courants", "optique", "dentaire"]),
    quantity=st.integers(min_value=1, max_value=12),
    tariffs=st.just(()),
).map(lambda i: replace(i, tariffs=TARIFFS.get(i.act_code, ())))

members = st.builds(
    MemberFacts,
    status=st.sampled_from(["actif", "carence", "suspendu"]),
    enrolled_on=st.dates(min_value=date(2023, 1, 1), max_value=date(2026, 12, 31)),
    unpaid_days=st.integers(min_value=0, max_value=120),
)

periods = st.builds(
    lambda start, length: Period(start, None if length is None else start + timedelta(length)),
    st.dates(min_value=date(2023, 1, 1), max_value=date(2026, 12, 31)),
    st.none() | st.integers(min_value=0, max_value=900),
)

providers = st.builds(
    ProviderFacts,
    active=st.booleans(),
    conventions=st.lists(periods, max_size=3).map(tuple),
)

claim_facts = st.builds(
    ClaimFacts,
    plan_id=st.just(PLAN_ID),
    service_date=service_dates,
    evaluated_at=st.datetimes(
        min_value=datetime(2025, 1, 1), max_value=datetime(2027, 12, 31), timezones=st.just(UTC)
    ),
    member=members,
    provider=providers,
    items=st.lists(items, min_size=1, max_size=6).map(tuple),
    family_consumed_xof=st.integers(min_value=0, max_value=3_500_000),
    fraud_score=st.none() | st.decimals(min_value=0, max_value=1, places=3),
)


@settings(max_examples=400, deadline=None)
@given(claim_facts)
def test_meme_entree_meme_version_meme_decision(f: ClaimFacts) -> None:
    first = evaluate(f, CATALOG)
    again = evaluate(copy.deepcopy(f), copy.deepcopy(CATALOG))
    assert first == again
    assert evaluate(f, CATALOG) == first


@settings(max_examples=400, deadline=None)
@given(claim_facts)
def test_invariants_de_decision(f: ClaimFacts) -> None:
    d = evaluate(f, CATALOG)

    for amount in (d.total_xof, d.covered_xof, d.patient_share_xof):
        assert type(amount) is int
        assert amount >= 0
    assert d.covered_xof + d.patient_share_xof == d.total_xof
    assert d.currency == "XOF"
    assert d.reason_code == d.rule.code
    assert d.rule.code in DECIDING_CODES

    expected = {
        Outcome.ACCORDEE_AUTO: {"R-12"},
        Outcome.EN_REVUE: {"R-20"},
        Outcome.REFUSEE: {"R-01", "R-04", "R-07", "R-09"},
    }[d.outcome]
    assert d.rule.code in expected
    if d.outcome is Outcome.REFUSEE:
        assert d.covered_xof == 0
    assert (d.review_due_at is not None) == (d.outcome is Outcome.EN_REVUE)


@settings(max_examples=200, deadline=None)
@given(claim_facts, st.integers(min_value=1, max_value=400))
def test_la_date_de_traitement_ne_change_pas_la_decision(f: ClaimFacts, days_later: int) -> None:
    """Seule la date du soin choisit les versions ; traiter plus tard ne change rien (R3)."""
    early = evaluate(f, CATALOG)
    late = evaluate(replace(f, evaluated_at=f.evaluated_at + timedelta(days=days_later)), CATALOG)
    assert (early.outcome, early.rule, early.covered_xof, early.checks) == (
        late.outcome,
        late.rule,
        late.covered_xof,
        late.checks,
    )
