"""Fenêtres fixes de publication (CR-P2-02) : semaines civiles locales, lundi → dimanche.

Contre le recoupement de deux requêtes : toute période publiée est une réunion de semaines
ENTIÈRES et TERMINÉES ; deux périodes publiées ne diffèrent donc que de semaines entières, dont
chacune passe elle-même le seuil (vérifié en base, ``test_repository``). Une semaine dont un
événement a pu expirer, ou antérieure à la rotation de la clé de pseudonymisation, n'est pas
comptée : son contenu ne bouge plus une fois publié.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from api.metrics.windows import (
    aligned_period,
    event_floor,
    key_floor,
    retained_since,
    week_start,
)

ABIDJAN = ZoneInfo("Africa/Abidjan")
THURSDAY = date(2026, 10, 1)  # semaine du lundi 28/09 au dimanche 04/10


def test_semaine_civile_du_lundi() -> None:
    assert week_start(THURSDAY) == date(2026, 9, 28)
    assert week_start(date(2026, 9, 28)) == date(2026, 9, 28)
    assert week_start(date(2026, 10, 4)) == date(2026, 9, 28)


@pytest.mark.parametrize(
    ("start", "end", "today", "expected"),
    [
        pytest.param(
            date(2026, 9, 30),
            date(2026, 10, 14),
            date(2026, 10, 29),
            (date(2026, 9, 28), date(2026, 10, 18)),
            id="elargie-aux-semaines-entieres",
        ),
        pytest.param(
            date(2026, 9, 28),
            THURSDAY,
            THURSDAY,
            None,
            id="semaine-en-cours-jamais-publiee",
        ),
        pytest.param(
            date(2026, 9, 14),
            date(2026, 10, 1),
            date(2026, 10, 1),
            (date(2026, 9, 14), date(2026, 9, 27)),
            id="coupee-a-la-derniere-semaine-terminee",
        ),
        pytest.param(
            date(2026, 9, 21),
            date(2026, 9, 27),
            date(2026, 9, 28),
            (date(2026, 9, 21), date(2026, 9, 27)),
            id="semaine-terminee-la-veille",
        ),
    ],
)
def test_periode_alignee(
    start: date, end: date, today: date, expected: tuple[date, date] | None
) -> None:
    assert aligned_period(start, end, today) == expected


def test_deux_periodes_publiees_ne_different_que_de_semaines_entieres() -> None:
    """Quel que soit le découpage demandé, bornes sur lundi et dimanche (fenêtres disjointes)."""
    today = date(2027, 3, 1)
    for offset in range(60):
        start = date(2026, 10, 1) + timedelta(days=offset)
        for length in (0, 1, 6, 7, 13, 30):
            period = aligned_period(start, start + timedelta(days=length), today)
            assert period is not None
            assert period[0].weekday() == 0
            assert period[1].weekday() == 6
            assert (period[1] - period[0]).days % 7 == 6


def test_aucune_semaine_partiellement_expiree() -> None:
    """Première semaine dont TOUS les événements sont encore conservés (rétention 180 jours)."""
    now = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    since = retained_since(now, 180, ABIDJAN)
    assert since.weekday() == 0
    assert (since.hour, since.minute) == (0, 0)
    assert since > now - timedelta(days=180)  # rien de cette semaine n'a pu expirer
    assert since - timedelta(days=7) <= now - timedelta(days=180)  # la précédente, si


def test_borne_de_retention_exacte_sur_un_lundi() -> None:
    """Un événement posé lundi 00:00 expire exactement à ``now`` : sa semaine est exclue."""
    monday = datetime(2026, 4, 6, 0, 0, tzinfo=UTC)
    now = monday + timedelta(days=180)
    assert retained_since(now, 180, ABIDJAN) == monday + timedelta(days=7)


@pytest.mark.parametrize(
    ("rotated", "expected"),
    [
        pytest.param(date(2026, 10, 1), date(2026, 10, 5), id="jeudi-lundi-suivant"),
        pytest.param(date(2026, 10, 4), date(2026, 10, 5), id="dimanche-lendemain"),
        pytest.param(date(2026, 10, 5), date(2026, 10, 12), id="lundi-semaine-suivante"),
    ],
)
def test_rotation_de_cle_premier_lundi_strictement_apres(rotated: date, expected: date) -> None:
    floor = key_floor(rotated, ABIDJAN)
    assert floor is not None
    assert floor.date() == expected
    assert floor.tzinfo is not None
    assert (floor.hour, floor.minute) == (0, 0)


def test_sans_rotation_aucune_borne() -> None:
    assert key_floor(None, ABIDJAN) is None


def test_plancher_des_evenements_compte_semaines_retenues_et_rotation() -> None:
    since = datetime(2026, 9, 28, tzinfo=ABIDJAN)
    now = datetime(2026, 10, 15, 9, 0, tzinfo=UTC)
    assert event_floor(since, now, 180, None, ABIDJAN) == since
    rotated = event_floor(since, now, 180, date(2026, 10, 1), ABIDJAN)
    assert rotated == datetime(2026, 10, 5, tzinfo=ABIDJAN)
    assert event_floor(since, now, 10, None, ABIDJAN) == retained_since(now, 10, ABIDJAN)
    assert event_floor(since, now, 10, None, ABIDJAN) > since
