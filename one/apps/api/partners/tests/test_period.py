"""Période des espaces assureur et employeur (CR-P3-02) : même fenêtre que la mesure produit.

La période demandée est élargie aux semaines civiles ENTIÈRES qu'elle touche (lundi → dimanche,
fuseau de l'organisation) puis coupée à la dernière semaine TERMINÉE : la semaine en cours et le
futur ne sont jamais publiés. Deux périodes publiées ne diffèrent donc que de semaines entières :
les requêtes [J] puis [J, J+1] rendent la même période. Aucune semaine terminée : 422 VAL-01.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from api.core.errors import ValidationFailedError
from api.partners import period as period_module
from api.partners.period import resolve_period

ABIDJAN = "Africa/Abidjan"
THURSDAY = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)  # semaine du lundi 28/09 au dimanche 04/10
NEXT_THURSDAY = THURSDAY + timedelta(days=7)


def test_jour_j_et_j_plus_un_rendent_la_meme_periode() -> None:
    one = resolve_period(date(2026, 10, 1), date(2026, 10, 1), NEXT_THURSDAY, ABIDJAN)
    two = resolve_period(date(2026, 10, 1), date(2026, 10, 2), NEXT_THURSDAY, ABIDJAN)
    assert one == two
    assert (one.start, one.end) == (date(2026, 9, 28), date(2026, 10, 4))
    zone = ZoneInfo(ABIDJAN)
    assert one.since == datetime(2026, 9, 28, tzinfo=zone)
    assert one.until == datetime(2026, 10, 5, tzinfo=zone)


def test_semaine_en_cours_jamais_publiee() -> None:
    with pytest.raises(ValidationFailedError) as caught:
        resolve_period(date(2026, 10, 1), date(2026, 10, 1), THURSDAY, ABIDJAN)
    assert caught.value.errors[0].field == "to"


def test_fin_dans_le_futur_coupee_a_la_derniere_semaine_terminee() -> None:
    found = resolve_period(date(2026, 10, 1), date(2027, 9, 30), NEXT_THURSDAY, ABIDJAN)
    assert (found.start, found.end) == (date(2026, 9, 28), date(2026, 10, 4))


def test_periode_entierement_future_refusee() -> None:
    with pytest.raises(ValidationFailedError):
        resolve_period(date(2026, 11, 2), date(2026, 11, 30), NEXT_THURSDAY, ABIDJAN)


def test_periode_par_defaut_30_jours_alignee() -> None:
    found = resolve_period(None, None, NEXT_THURSDAY, ABIDJAN)
    assert found.start.weekday() == 0
    assert found.end == date(2026, 10, 4)
    assert found.end.weekday() == 6


@pytest.mark.parametrize(
    ("start", "end"),
    [
        pytest.param(date(2026, 10, 2), date(2026, 10, 1), id="debut-apres-fin"),
        pytest.param(date(2025, 9, 1), date(2026, 9, 30), id="plus-de-366-jours"),
    ],
)
def test_periode_invalide(start: date, end: date) -> None:
    with pytest.raises(ValidationFailedError):
        resolve_period(start, end, NEXT_THURSDAY, ABIDJAN)


def test_mutation_sans_alignement_la_semaine_en_cours_passerait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Témoin : sans l'alignement, la période [J] serait servie le jour même."""
    monkeypatch.setattr(period_module, "aligned_period", lambda start, end, _today: (start, end))
    found = resolve_period(date(2026, 10, 1), date(2026, 10, 1), THURSDAY, ABIDJAN)
    assert found.start == found.end == date(2026, 10, 1)
