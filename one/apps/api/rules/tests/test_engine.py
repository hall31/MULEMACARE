"""Moteur de règles pur (L2) : critères R3, R4, R5 du PRD §4, règles du PRD §5."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from api.rules.engine import evaluate
from api.rules.errors import InvalidRuleParamsError, NoVersionInForceError, OverlappingVersionsError
from api.rules.model import Catalog, MemberFacts, Outcome, Period, ProviderFacts
from api.rules.tests.builders import (
    CATALOG,
    PLAN_HISTORY,
    PLAN_V1_ID,
    PLAN_V2_ID,
    RULE_HISTORY,
    RULE_IDS,
    Y2026,
    facts,
    item,
    rule,
)

# 25 000 + 15 000 + 8 000 = 48 000 FCFA (barème 2026).
ITEMS_48K = (item("CONS-GEN"), item("CARD-ECG"), item("BIO-NFS"))
# 35 000 + 5 x 30 000 = 185 000 FCFA.
ITEMS_185K = (item("CONS-SPE"), item("IMG-ECHO-ABD", quantity=5))


# ---------------------------------------------------------------- R5 : R-12 / R-20


def test_48000_fcfa_score_006_accorde_automatiquement() -> None:
    decision = evaluate(facts(*ITEMS_48K, fraud_score="0.06"), CATALOG)

    assert decision.outcome is Outcome.ACCORDEE_AUTO
    assert decision.reason_code == "R-12"
    assert (decision.rule.rule_id, decision.rule.code, decision.rule.version) == (
        RULE_IDS["R-12"],
        "R-12",
        3,
    )
    assert decision.total_xof == 48_000
    assert decision.covered_xof == 38_400  # 80 % (proto)
    assert decision.patient_share_xof == 9_600
    assert decision.review_due_at is None


def test_185000_fcfa_part_en_revue_avec_delai_cible() -> None:
    f = facts(*ITEMS_185K, fraud_score="0.06")
    decision = evaluate(f, CATALOG)

    assert decision.outcome is Outcome.EN_REVUE
    assert (decision.reason_code, decision.rule.code, decision.rule.version) == ("R-20", "R-20", 2)
    assert decision.rule.rule_id == RULE_IDS["R-20"]
    assert decision.total_xof == 185_000
    assert decision.review_due_at == f.evaluated_at + timedelta(minutes=120)


def test_seuil_50000_exclu_part_en_revue() -> None:
    decision = evaluate(facts(item("CONS-GEN", quantity=2)), CATALOG)
    assert decision.total_xof == 50_000
    assert decision.outcome is Outcome.EN_REVUE


def test_score_020_exclu_part_en_revue() -> None:
    assert evaluate(facts(*ITEMS_48K, fraud_score="0.20"), CATALOG).outcome is Outcome.EN_REVUE
    assert (
        evaluate(facts(*ITEMS_48K, fraud_score="0.199"), CATALOG).outcome is Outcome.ACCORDEE_AUTO
    )


def test_score_absent_part_en_revue() -> None:
    assert evaluate(facts(*ITEMS_48K, fraud_score=None), CATALOG).outcome is Outcome.EN_REVUE


# ---------------------------------------------------------------- R4 : refus à code stable


def test_droits_suspendus_refus_r01() -> None:
    member = MemberFacts(status="suspendu", enrolled_on=date(2024, 3, 1), unpaid_days=50)
    decision = evaluate(facts(*ITEMS_48K, member=member), CATALOG)
    assert decision.outcome is Outcome.REFUSEE
    assert (decision.reason_code, decision.rule.code, decision.rule.version) == ("R-01", "R-01", 2)
    assert decision.rule.rule_id == RULE_IDS["R-01"]
    assert decision.covered_xof == 0
    assert decision.patient_share_xof == decision.total_xof == 48_000


def test_impaye_45_jours_refus_r01_meme_si_statut_pas_encore_bascule() -> None:
    member = MemberFacts(status="actif", enrolled_on=date(2024, 3, 1), unpaid_days=45)
    assert evaluate(facts(member=member), CATALOG).reason_code == "R-01"
    member_44 = replace(member, unpaid_days=44)
    assert evaluate(facts(member=member_44), CATALOG).outcome is Outcome.ACCORDEE_AUTO


def test_hors_reseau_refus_r04() -> None:
    provider = ProviderFacts(active=True, conventions=())
    decision = evaluate(facts(*ITEMS_48K, provider=provider), CATALOG)
    assert decision.outcome is Outcome.REFUSEE
    assert (decision.reason_code, decision.rule.code, decision.rule.version) == ("R-04", "R-04", 2)


def test_convention_expiree_a_la_date_du_soin_refus_r04() -> None:
    provider = ProviderFacts(
        active=True, conventions=(Period(date(2024, 1, 1), date(2026, 5, 31)),)
    )
    assert evaluate(facts(provider=provider), CATALOG).reason_code == "R-04"


def test_prestataire_suspendu_refus_r04() -> None:
    provider = ProviderFacts(active=False, conventions=(Period(date(2024, 1, 1), None),))
    assert evaluate(facts(provider=provider), CATALOG).reason_code == "R-04"


def test_acte_hors_bareme_a_la_date_refus_r04() -> None:
    decision = evaluate(facts(item("CONS-GEN"), item("ACTE-INCONNU")), CATALOG)
    assert decision.outcome is Outcome.REFUSEE
    assert decision.reason_code == "R-04"
    assert decision.total_xof == 25_000  # seules les lignes au barème ont un montant


def test_carence_en_cours_refus_r07() -> None:
    member = MemberFacts(status="actif", enrolled_on=date(2026, 5, 1), unpaid_days=0)
    decision = evaluate(facts(member=member, service_date=date(2026, 6, 29)), CATALOG)
    assert decision.outcome is Outcome.REFUSEE
    assert (decision.reason_code, decision.rule.code, decision.rule.version) == ("R-07", "R-07", 2)


def test_carence_ecoulee_au_60e_jour() -> None:
    member = MemberFacts(status="actif", enrolled_on=date(2026, 5, 1), unpaid_days=0)
    # 01/05 + 60 jours = 30/06 (durée portée par la version de produit v2).
    decision = evaluate(facts(member=member, service_date=date(2026, 6, 30)), CATALOG)
    assert decision.outcome is Outcome.ACCORDEE_AUTO


def test_plafond_familial_insuffisant_refus_r09() -> None:
    # Couvert 38 400 FCFA ; reste 3 000 000 - 2 970 000 = 30 000 FCFA.
    decision = evaluate(facts(*ITEMS_48K, family_consumed_xof=2_970_000), CATALOG)
    assert decision.outcome is Outcome.REFUSEE
    assert (decision.reason_code, decision.rule.code, decision.rule.version) == ("R-09", "R-09", 2)


def test_plafond_tout_juste_suffisant() -> None:
    decision = evaluate(facts(*ITEMS_48K, family_consumed_xof=3_000_000 - 38_400), CATALOG)
    assert decision.outcome is Outcome.ACCORDEE_AUTO


def test_ordre_des_refus_r01_avant_r04() -> None:
    member = MemberFacts(status="suspendu", enrolled_on=date(2024, 3, 1), unpaid_days=0)
    provider = ProviderFacts(active=True, conventions=())
    decision = evaluate(facts(member=member, provider=provider), CATALOG)
    assert decision.reason_code == "R-01"
    assert [(c.rule.code, c.passed) for c in decision.checks] == [
        ("R-01", False),
        ("R-04", False),
        ("R-07", True),
        ("R-09", True),
    ]


# ---------------------------------------------------------------- R3 : version à la date du soin


def test_regle_modifiee_au_01_01_soin_du_20_12_traite_le_05_01() -> None:
    """R-12 passe de 40 000 (v2) à 50 000 (v3) le 01/01/2026 ; le produit de v1 à v2."""
    processed_on = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
    # Barème 2025 : 22 000 + 15 000 + 8 000 = 45 000 ; barème 2026 : 48 000.
    items = ITEMS_48K

    old = evaluate(
        facts(*items, service_date=date(2025, 12, 20), evaluated_at=processed_on), CATALOG
    )
    assert old.total_xof == 45_000
    assert old.plan_version_id == PLAN_V1_ID
    assert old.outcome is Outcome.EN_REVUE  # 45 000 ≥ 40 000 (R-12 v2)
    checks = {c.rule.code: c.rule.version for c in old.checks}
    assert checks["R-12"] == 2
    assert checks["R-01"] == 1

    # Le même soin daté du jour de traitement relève de R-12 v3 et du produit v2.
    new = evaluate(facts(*items, service_date=date(2026, 1, 5), evaluated_at=processed_on), CATALOG)
    assert new.plan_version_id == PLAN_V2_ID
    assert new.outcome is Outcome.ACCORDEE_AUTO
    assert (new.rule.code, new.rule.version) == ("R-12", 3)


def test_version_brouillon_jamais_appliquee() -> None:
    with pytest.raises(NoVersionInForceError) as exc:
        evaluate(facts(service_date=date(2027, 2, 1)), CATALOG)
    assert exc.value.code == "NOT-01"


def test_regle_manquante_a_la_date() -> None:
    catalog = Catalog(PLAN_HISTORY, tuple(r for r in RULE_HISTORY if r.code != "R-09"))
    with pytest.raises(NoVersionInForceError) as exc:
        evaluate(facts(), catalog)
    assert "R-09" in exc.value.message


def test_versions_publiees_chevauchantes_refusees() -> None:
    clash = rule("R-12", 4, Period(date(2026, 6, 1), None), {"total_max_exclu_xof": 1})
    with pytest.raises(OverlappingVersionsError) as exc:
        evaluate(facts(), Catalog(PLAN_HISTORY, (*RULE_HISTORY, clash)))
    assert exc.value.code == "RUL-02"


def test_version_soumise_ignoree() -> None:
    submitted = rule(
        "R-12", 4, Period(date(2026, 6, 1), None), {"total_max_exclu_xof": 1}, "soumise"
    )
    decision = evaluate(facts(*ITEMS_48K), Catalog(PLAN_HISTORY, (*RULE_HISTORY, submitted)))
    assert (decision.rule.code, decision.rule.version) == ("R-12", 3)


# ---------------------------------------------------------------- règles en données


@pytest.mark.parametrize(
    "params",
    [
        {"total_max_exclu_xof": 50000.0, "score_fraude_max_exclu": 0.2},  # montant flottant
        {"total_max_exclu_xof": True, "score_fraude_max_exclu": 0.2},  # booléen
        {"total_max_exclu_xof": 50000},  # score manquant
        {"total_max_exclu_xof": 50000, "score_fraude_max_exclu": 0.2, "inconnu": 1},
        {"total_max_exclu_xof": -1, "score_fraude_max_exclu": 0.2},
    ],
)
def test_parametres_invalides_refuses(params: dict[str, object]) -> None:
    bad = rule("R-12", 3, Y2026, params)
    catalog = Catalog(
        PLAN_HISTORY, tuple(bad if r.code == "R-12" and r.version == 3 else r for r in RULE_HISTORY)
    )
    with pytest.raises(InvalidRuleParamsError) as exc:
        evaluate(facts(), catalog)
    assert exc.value.code == "VAL-01"


def test_seuil_change_par_la_donnee_seule() -> None:
    raised = rule("R-12", 3, Y2026, {"total_max_exclu_xof": 200_000, "score_fraude_max_exclu": 0.2})
    catalog = Catalog(
        PLAN_HISTORY,
        tuple(raised if r.code == "R-12" and r.version == 3 else r for r in RULE_HISTORY),
    )
    assert evaluate(facts(*ITEMS_185K), catalog).outcome is Outcome.ACCORDEE_AUTO


def test_taux_de_garantie_propre_et_arrondi_entier() -> None:
    from api.rules.model import Coverage  # noqa: PLC0415

    v2 = next(p for p in PLAN_HISTORY if p.version == 2)
    optics = replace(v2, coverages=(*v2.coverages[:2], Coverage("optique", 3333)))
    catalog = Catalog((optics,), RULE_HISTORY)
    decision = evaluate(facts(item("CONS-GEN"), item("IMG-RX-THO", category="optique")), catalog)
    # 25 000 x 80 % = 20 000 ; 18 000 x 33,33 % = 5 999,4 → 5 999 (arrondi inférieur par ligne).
    assert decision.covered_xof == 20_000 + 5_999
    assert isinstance(decision.covered_xof, int)
    assert decision.covered_xof + decision.patient_share_xof == decision.total_xof


# ---------------------------------------------------------------- enregistrement de la décision


def test_decision_porte_rule_id_et_rule_version_pour_claim_decisions() -> None:
    decision = evaluate(facts(*ITEMS_185K), CATALOG)
    record = decision.as_claim_decision()

    assert record["source"] == "regle"
    assert record["outcome"] == "en_revue"
    assert record["rule_id"] == RULE_IDS["R-20"]
    assert record["rule_version"] == 2
    assert record["reason_code"] == "R-20"
    trace = record["evaluation_trace"]
    assert isinstance(trace, list)
    assert [(t["rule_code"], t["rule_version"], t["passed"]) for t in trace] == [
        ("R-01", 2, True),
        ("R-04", 2, True),
        ("R-07", 2, True),
        ("R-09", 2, True),
        ("R-12", 3, False),
    ]
    assert all(str(t["rule_id"]) for t in trace)


def test_chaque_verification_cite_sa_regle_et_sa_version() -> None:
    decision = evaluate(facts(*ITEMS_48K), CATALOG)
    for check in decision.checks:
        assert check.rule.rule_id == RULE_IDS[check.rule.code]
        assert check.rule.version >= 1
        assert check.message


def test_periode_2026_ouverte() -> None:
    assert Y2026.contains(date(2099, 1, 1))
    assert not Y2026.contains(date(2025, 12, 31))
