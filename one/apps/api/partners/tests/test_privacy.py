"""k-anonymat des espaces assureur et employeur (CR-P3-01, CR-P3-02), y compris contre la
soustraction.

Règles (même méthode que ``api.metrics``, CR-P2-02) :

- une valeur portée par moins de 5 personnes distinctes est masquée (ni valeur, ni effectif) ;
- elle l'est aussi si UNE semaine non vide de la période en a moins de 5 : deux périodes
  publiées ne diffèrent que de semaines entières, chacune doit passer le seuil, sinon la
  différence des deux réponses isolerait sa contribution ;
- rien n'est publié exact : effectifs ET comptes (adhérents, dossiers) par palier (5, 10, 20, 50,
  100), montants arrondis au millier de francs CFA ;
- un tableau publie des PARTIES et leur TOTAL : les cellules masquées réunies doivent elles-mêmes
  passer le seuil (semaine par semaine), sinon total - cellules visibles révélerait la cellule
  masquée. Des cellules visibles (les plus petites) sont alors masquées ou fondues dans
  « autres ».
Données fictives.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest

from api.metrics.privacy import K_ANONYMITY as METRICS_K
from api.partners import privacy
from api.partners.privacy import (
    AMOUNT_STEP_XOF,
    K_ANONYMITY,
    OTHERS,
    Cell,
    amount_value,
    count_value,
    fold_cells,
    mask_cells,
    measure_value,
    merge,
    rounded_amount,
)

W1 = date(2026, 9, 28)
W2 = W1 + timedelta(days=7)


def _people(n: int) -> frozenset[UUID]:
    return frozenset(uuid4() for _ in range(n))


def _cell(key: str, people: int, amount: int = 0, count: int | None = None) -> Cell:
    group = _people(people)
    return Cell(key, count if count is not None else people, amount, group, {W1: group})


def _two_weeks(key: str, strong: int, weak: int, amount: int = 0) -> Cell:
    first, second = _people(strong), _people(weak)
    return Cell(key, strong + weak, amount, first | second, {W1: first, W2: second})


def test_seuil_identique_a_la_mesure_produit() -> None:
    assert K_ANONYMITY == METRICS_K == 5


@pytest.mark.parametrize(("people", "status"), [(4, "masque"), (5, "disponible"), (0, "masque")])
def test_valeur_masquee_sous_le_seuil(people: int, status: str) -> None:
    value = amount_value(_cell("x", people, 12_000))
    assert value.status == status
    if status == "masque":
        assert (value.value, value.contributors) == (None, None)
    else:
        assert (value.value, value.contributors) == (12_000, 5)


@pytest.mark.parametrize(("people", "band"), [(5, 5), (9, 5), (10, 10), (37, 20), (512, 100)])
def test_effectif_publie_par_palier(people: int, band: int) -> None:
    assert amount_value(_cell("x", people, 1_000)).contributors == band


@pytest.mark.parametrize(("count", "band"), [(5, 5), (8, 5), (11, 10), (49, 20), (100, 100)])
def test_compte_publie_par_palier_jamais_exact(count: int, band: int) -> None:
    """Adhérents, dossiers : un de plus ne se voit pas d'une requête à l'autre (sauf palier)."""
    value = count_value(_cell("x", 5, count=count))
    assert (value.status, value.value, value.contributors) == ("disponible", band, 5)


@pytest.mark.parametrize(
    ("amount", "published"),
    [(0, 0), (499, 0), (500, 1_000), (326_400, 326_000), (16_000, 16_000), (1_234_567, 1_235_000)],
)
def test_montant_arrondi_au_millier(amount: int, published: int) -> None:
    assert AMOUNT_STEP_XOF == 1_000
    assert rounded_amount(amount) == published
    assert amount_value(_cell("x", 6, amount)).value == published


def test_semaine_faible_masque_toute_la_periode() -> None:
    """Semaine 1 : 8 personnes, semaine 2 : 1 personne. [S1] publié, [S1, S2] masqué : la
    différence des deux réponses isolerait le dossier de la seule personne de S2."""
    alone = _two_weeks("total", strong=8, weak=1, amount=100_000)
    assert len(alone.people) == 9
    assert amount_value(alone).status == "masque"
    assert count_value(alone).status == "masque"
    assert measure_value(5_000, alone.people, alone.weeks).status == "masque"


def test_semaines_toutes_au_seuil_publiees() -> None:
    both = _two_weeks("total", strong=8, weak=5, amount=100_000)
    assert amount_value(both).status == "disponible"


def test_mutation_semaine_faible_ignoree(monkeypatch: pytest.MonkeyPatch) -> None:
    """Témoin : sans la règle par semaine, la période [S1, S2] serait publiée."""
    monkeypatch.setattr(privacy, "weakest_week", lambda cell: len(cell.people))
    assert amount_value(_two_weeks("total", strong=8, weak=1, amount=1_000)).status == "disponible"


def test_instantane_sans_semaine_juge_sur_l_effectif() -> None:
    """Statuts d'adhérents (instantané à la fin de la période) : pas de semaine, seuil seul."""
    snapshot = Cell("actif", 6, 0, _people(6))
    assert count_value(snapshot).value == 5


def test_cellule_isolee_sous_le_seuil_entraine_un_masque_voisin() -> None:
    """actif 10, carence 2, suspendu 0 : total publié ; masquer carence seule la révèle."""
    cells = [_cell("actif", 10), _cell("carence", 2), _cell("suspendu", 0)]
    shown = mask_cells(cells)
    assert shown == {"actif": False, "carence": False, "suspendu": False}


def test_cellules_masquees_assez_nombreuses_ensemble() -> None:
    """actif 20, carence 3, suspendu 3 : les deux masquées portent 6 personnes : actif reste."""
    cells = [_cell("actif", 20), _cell("carence", 3), _cell("suspendu", 3)]
    assert mask_cells(cells) == {"actif": True, "carence": False, "suspendu": False}


def test_toutes_publiees_au_dessus_du_seuil() -> None:
    cells = [_cell("actif", 9), _cell("carence", 5), _cell("suspendu", 6)]
    assert mask_cells(cells) == {"actif": True, "carence": True, "suspendu": True}


def test_categories_sous_le_seuil_fondues_dans_autres() -> None:
    cells = [
        _cell("soins_courants", 12, 400_000),
        _cell("optique", 6, 90_000),
        _cell("maternite", 2, 300_000),
        _cell("dentaire", 3, 50_000),
    ]
    shown, other = fold_cells(cells)
    assert [c.key for c in shown] == ["soins_courants", "optique"]
    assert other is not None
    assert other.key == OTHERS
    assert len(other.people) == 5
    assert other.amount == 350_000


def test_categorie_a_semaine_faible_fondue_dans_autres() -> None:
    """Optique : 6 personnes sur la période mais 1 seule en S2 : jamais citée seule."""
    cells = [
        _cell("soins_courants", 12, 400_000),
        _two_weeks("optique", strong=5, weak=1, amount=90_000),
        _cell("dentaire", 6, 50_000),
    ]
    shown, other = fold_cells(cells)
    assert "optique" not in [c.key for c in shown]
    assert other is not None
    # « autres » doit passer le seuil semaine par semaine : S2 n'a qu'une personne, donc on y
    # fond des cellules visibles jusqu'à tout fondre, puis « autres » est masqué.
    assert amount_value(other).status == "masque"


def test_autres_trop_petit_absorbe_la_plus_petite_categorie_visible() -> None:
    """« autres » à 2 personnes : on y fond la plus petite visible, sinon total - visibles = 2."""
    cells = [
        _cell("soins_courants", 12, 400_000),
        _cell("optique", 6, 90_000),
        _cell("maternite", 2, 300_000),
    ]
    shown, other = fold_cells(cells)
    assert [c.key for c in shown] == ["soins_courants"]
    assert other is not None
    assert len(other.people) == 8
    assert amount_value(other).status == "disponible"


def test_personnes_communes_a_plusieurs_categories_comptees_une_fois() -> None:
    """Le seuil porte sur des personnes DISTINCTES, pas sur une somme d'effectifs."""
    same = _people(3)
    cells = [
        _cell("soins_courants", 10, 100_000),
        Cell("optique", 3, 1_000, same, {W1: same}),
        Cell("dentaire", 3, 1_000, same, {W1: same}),
    ]
    shown, other = fold_cells(cells)
    assert other is not None
    assert len(other.people) >= K_ANONYMITY
    assert [c.key for c in shown] == []


def test_fusion_reunit_les_personnes_semaine_par_semaine() -> None:
    a, b = _two_weeks("a", 5, 2), _two_weeks("b", 5, 3)
    merged = merge([a, b])
    assert len(merged.weeks[W2]) == 5
    assert merged.count == a.count + b.count


def test_classement_borne_et_reste_fondu() -> None:
    cells = [_cell(f"p{i}", 5 + i, 1000 * (10 - i)) for i in range(8)]
    shown, other = fold_cells(cells, limit=5)
    assert [c.key for c in shown] == ["p0", "p1", "p2", "p3", "p4"]
    assert other is not None
    assert other.key == OTHERS
    assert other.amount == 5000 + 4000 + 3000


def test_sans_reste_pas_de_ligne_autres() -> None:
    shown, other = fold_cells([_cell("soins_courants", 7, 10)])
    assert [c.key for c in shown] == ["soins_courants"]
    assert other is None


def test_mutation_seuil_abaisse_la_cellule_isolee_apparait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Témoin : seuil ramené à 1, carence (2 personnes) serait publiée ; la garde est porteuse."""
    monkeypatch.setattr(privacy, "K_ANONYMITY", 1)
    cells = [_cell("actif", 10), _cell("carence", 2), _cell("suspendu", 1)]
    assert mask_cells(cells) == {"actif": True, "carence": True, "suspendu": True}
