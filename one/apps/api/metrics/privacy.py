"""Seuil de k-anonymat et publication des agrégats (CR-P2-01, CR-P2-02).

Un indicateur est ``masque`` (ni valeur, ni effectif) si moins de ``K_ANONYMITY`` personnes le
portent sur la période, OU si une semaine non vide de la période en a moins
(``weakest_window``) : deux périodes publiées ne diffèrent que de semaines entières
(``windows``), et chacune de ces semaines doit elle-même passer le seuil, sinon la différence
des deux réponses isolerait sa contribution. Le seuil est un plancher fixe, pas un réglage.

L'effectif publié n'est jamais exact : c'est le plancher de son palier (5, 10, 20, 50, 100 ;
« 100 » vaut « 100 ou plus »). Un contributeur de plus ne se voit donc pas d'une requête à
l'autre. Taux en points de base, arrondis à l'entier le plus proche par arithmétique entière.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from api.metrics.schemas import MetricKey, MetricUnit, ProductMetric

K_ANONYMITY: Final = 5
CONTRIBUTOR_BANDS: Final = (5, 10, 20, 50, 100)
BASIS_POINTS: Final = 10_000

UNITS: Final[Mapping[MetricKey, MetricUnit]] = MappingProxyType(
    {
        "claims_auto_approved_rate": "pour_dix_mille",
        "claims_review_rate": "pour_dix_mille",
        "claims_decision_median_ms": "millisecondes",
        "counter_decision_display_median_ms": "millisecondes",
        "onboarding_completion_rate": "pour_dix_mille",
        "first_card_median_ms": "millisecondes",
        "payment_links_paid_rate": "pour_dix_mille",
        "ledger_balance_gap_xof": "xof",
        "webhook_duplicate_rate": "pour_dix_mille",
    }
)


def contributor_band(contributors: int) -> int:
    """Plancher du palier de ``contributors`` (au moins le seuil)."""
    if contributors < K_ANONYMITY:
        msg = f"effectif sous le seuil de k-anonymat ({K_ANONYMITY}) : rien à publier"
        raise ValueError(msg)
    return max(band for band in CONTRIBUTOR_BANDS if band <= contributors)


def _publish(
    key: MetricKey, value: int | None, contributors: int, weakest_window: int
) -> ProductMetric:
    if value is None or min(contributors, weakest_window) < K_ANONYMITY:
        return ProductMetric(
            key=key, unit=UNITS[key], status="masque", value=None, contributors=None
        )
    return ProductMetric(
        key=key,
        unit=UNITS[key],
        status="disponible",
        value=value,
        contributors=contributor_band(contributors),
    )


def rate_metric(
    key: MetricKey, numerator: int, denominator: int, contributors: int, weakest_window: int
) -> ProductMetric:
    """Taux en points de base, arrondi au plus proche (demi vers le haut)."""
    if denominator <= 0:
        return _publish(key, None, contributors, weakest_window)
    value = (2 * BASIS_POINTS * numerator + denominator) // (2 * denominator)
    return _publish(key, value, contributors, weakest_window)


def median_metric(
    key: MetricKey, value: int | None, contributors: int, weakest_window: int
) -> ProductMetric:
    return _publish(key, value, contributors, weakest_window)


def total_metric(
    key: MetricKey, value: int, contributors: int, weakest_window: int
) -> ProductMetric:
    return _publish(key, value, contributors, weakest_window)
