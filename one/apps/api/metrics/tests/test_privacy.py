"""Seuil de k-anonymat (k = 5), paliers d'effectif et arithmétique entière (P2, CR-P2-01/02).

Un indicateur n'est publié que si l'effectif de la période ET celui de CHAQUE semaine non vide
de la période atteignent le seuil (``weakest_window``) : sinon deux périodes publiées pourraient
différer d'une semaine portée par une seule personne. L'effectif publié est le plancher d'un
palier (5, 10, 20, 50, 100), jamais le compte exact.
"""

from __future__ import annotations

import pytest

from api.metrics.privacy import (
    CONTRIBUTOR_BANDS,
    K_ANONYMITY,
    contributor_band,
    median_metric,
    rate_metric,
    total_metric,
)


def test_seuil_de_k_anonymat_fixe_a_cinq() -> None:
    assert K_ANONYMITY == 5
    assert CONTRIBUTOR_BANDS[0] == K_ANONYMITY


@pytest.mark.parametrize("contributors", [0, 1, 4])
def test_moins_de_cinq_contributeurs_masque_tout(contributors: int) -> None:
    for metric in (
        rate_metric("claims_auto_approved_rate", 1, 1, contributors, contributors),
        median_metric("claims_decision_median_ms", 1200, contributors, contributors),
        total_metric("ledger_balance_gap_xof", 0, contributors, contributors),
    ):
        assert (metric.status, metric.value, metric.contributors) == ("masque", None, None)


@pytest.mark.parametrize("weakest", [1, 4])
def test_une_semaine_sous_le_seuil_masque_toute_la_periode(weakest: int) -> None:
    """Le complément d'une période (une semaine à une personne) ne doit pas être déductible."""
    for metric in (
        rate_metric("claims_auto_approved_rate", 1, 6, 12, weakest),
        median_metric("counter_decision_display_median_ms", 5000, 6, weakest),
        total_metric("ledger_balance_gap_xof", 0, 30, weakest),
    ):
        assert (metric.status, metric.value, metric.contributors) == ("masque", None, None)


def test_cinq_contributeurs_publie_la_valeur() -> None:
    metric = rate_metric("claims_auto_approved_rate", 2, 6, 5, 5)
    assert (metric.status, metric.value, metric.contributors) == ("disponible", 3333, 5)
    assert metric.unit == "pour_dix_mille"


@pytest.mark.parametrize(
    ("exact", "band"),
    [
        (5, 5),
        (6, 5),
        (9, 5),
        (10, 10),
        (19, 10),
        (20, 20),
        (49, 20),
        (50, 50),
        (99, 50),
        (100, 100),
        (12_345, 100),
    ],
)
def test_effectif_publie_par_palier_jamais_exact(exact: int, band: int) -> None:
    assert contributor_band(exact) == band
    assert median_metric("first_card_median_ms", 1, exact, exact).contributors == band


def test_un_contributeur_de_plus_ne_change_pas_l_effectif_publie() -> None:
    """Attaque du vérificateur : effectif 5 → 6 visible. Désormais 5 → 5."""
    before = median_metric("counter_decision_display_median_ms", 6000, 5, 5)
    after = median_metric("counter_decision_display_median_ms", 6000, 6, 6)
    assert before.contributors == after.contributors == 5


def test_palier_sous_le_seuil_refuse() -> None:
    with pytest.raises(ValueError, match="seuil"):
        contributor_band(4)


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [(5, 6, 8333), (1, 6, 1667), (0, 7, 0), (7, 7, 10_000), (1, 3, 3333), (2, 3, 6667)],
)
def test_taux_en_points_de_base_arrondi_entier(
    numerator: int, denominator: int, expected: int
) -> None:
    metric = rate_metric("payment_links_paid_rate", numerator, denominator, 9, 9)
    assert metric.value == expected
    assert isinstance(metric.value, int)


def test_denominateur_nul_masque_meme_avec_contributeurs() -> None:
    assert rate_metric("claims_review_rate", 0, 0, 9, 9).status == "masque"


def test_mediane_absente_masquee() -> None:
    assert median_metric("first_card_median_ms", None, 9, 9).status == "masque"


def test_unites() -> None:
    assert median_metric("claims_decision_median_ms", 10, 5, 5).unit == "millisecondes"
    assert total_metric("ledger_balance_gap_xof", -3, 5, 5).unit == "xof"
    assert total_metric("ledger_balance_gap_xof", -3, 5, 5).value == -3
