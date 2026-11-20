"""k-anonymat des espaces assureur et employeur (CR-P3-01, CR-P3-02).

Même méthode que la mesure produit (``api.metrics.privacy`` et ``api.metrics.windows``) :

- seuil : une valeur portée par moins de ``K_ANONYMITY`` (5) personnes DISTINCTES est ``masque``
  (ni valeur, ni effectif) ;
- semaines : la période publiée est faite de semaines civiles entières et terminées
  (``api.partners.period``) ; une valeur est aussi masquée si UNE semaine non vide de la période
  a moins de 5 personnes (``weakest_week``). Deux périodes publiées ne diffèrent que de semaines
  entières, chacune au seuil : leur différence n'isole personne ;
- jamais exact : effectif ET comptes (adhérents, dossiers) publiés par palier
  (``contributor_band`` : 5, 10, 20, 50, 100) ; montants arrondis au millier de francs CFA
  (``AMOUNT_STEP_XOF``), pour que la différence de deux montants ne rende pas un montant exact.

Un tableau publie des parties ET leur total. Masquer une seule petite cellule ne suffit donc
pas : total - cellules visibles la révélerait. Deux règles :

- ``mask_cells`` (liste fixe et connue, par exemple les trois statuts d'adhérent) : si les
  cellules masquées réunies ne passent pas le seuil, les plus petites cellules visibles sont
  masquées à leur tour, jusqu'au seuil ou jusqu'à tout masquer ;
- ``fold_cells`` (liste ouverte : catégories de garantie, prestataires) : une cellule sous le
  seuil n'est pas citée du tout (sa seule présence est une information) ; elle est fondue dans
  « autres ». Si « autres » ne passe pas le seuil, la plus petite cellule visible y est fondue à
  son tour. ``limit`` borne un classement (les autres rejoignent « autres »).

Les personnes sont des identifiants pseudonymes internes (UUID) qui ne quittent pas le service :
seuls des effectifs et des sommes sont publiés.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Final
from uuid import UUID

from api.metrics.privacy import K_ANONYMITY as _METRICS_K
from api.metrics.privacy import contributor_band
from api.partners.schemas import KValue

K_ANONYMITY: int = _METRICS_K
AMOUNT_STEP_XOF: Final = 1_000
OTHERS: Final = "autres_regroupes"

type People = frozenset[UUID]
type Weeks = Mapping[date, People]


@dataclass(frozen=True, slots=True)
class Cell:
    """Cellule d'un tableau : clé, compte (dossiers, adhérents), montant, personnes.

    ``weeks`` : personnes de chaque semaine (lundi) où la cellule a une ligne déterminante
    (demande, décision, paiement). Vide pour un instantané (statuts à la fin de la période).
    """

    key: str
    count: int
    amount: int
    people: People
    weeks: Weeks = field(default_factory=dict)


def weakest_week(cell: Cell) -> int:
    """Effectif de la semaine non vide la plus faible ; l'effectif total pour un instantané."""
    return min((len(p) for p in cell.weeks.values() if p), default=len(cell.people))


def _passes(cell: Cell) -> bool:
    return min(len(cell.people), weakest_week(cell)) >= K_ANONYMITY


def rounded_amount(amount: int) -> int:
    """Millier de francs CFA le plus proche (demi vers le haut), arithmétique entière."""
    return (amount + AMOUNT_STEP_XOF // 2) // AMOUNT_STEP_XOF * AMOUNT_STEP_XOF


def masked() -> KValue:
    return KValue(status="masque", value=None, contributors=None)


def _publish(value: int, contributors: int, weakest: int) -> KValue:
    if min(contributors, weakest) < K_ANONYMITY:
        return masked()
    # Effectif publié par palier (5, 10, 20, 50, 100), jamais exact : même règle que P2.
    return KValue(status="disponible", value=value, contributors=contributor_band(contributors))


def count_value(cell: Cell) -> KValue:
    """Compte (adhérents, dossiers) publié par palier, jamais exact."""
    if not _passes(cell):
        return masked()
    return _publish(contributor_band(cell.count), len(cell.people), weakest_week(cell))


def amount_value(cell: Cell) -> KValue:
    """Montant en francs CFA, arrondi au millier."""
    return _publish(rounded_amount(cell.amount), len(cell.people), weakest_week(cell))


def measure_value(value: int | None, people: People, weeks: Weeks) -> KValue:
    """Taux (points de base) ou délai moyen : valeur telle quelle, mêmes seuils."""
    if value is None:
        return masked()
    return _publish(value, len(people), weakest_week(Cell("mesure", 0, 0, people, weeks)))


def _union(cells: Iterable[Cell]) -> People:
    found: People = frozenset()
    for cell in cells:
        found |= cell.people
    return found


def merge(cells: Sequence[Cell], key: str = OTHERS) -> Cell:
    """Réunion de cellules : personnes réunies semaine par semaine (comptées une fois)."""
    weeks: dict[date, People] = {}
    for cell in cells:
        for week, people in cell.weeks.items():
            weeks[week] = weeks.get(week, frozenset()) | people
    return Cell(
        key=key,
        count=sum(c.count for c in cells),
        amount=sum(c.amount for c in cells),
        people=_union(cells),
        weeks=weeks,
    )


def _size(cell: Cell) -> tuple[int, int, str]:
    return (len(cell.people), cell.amount, cell.key)


def mask_cells(cells: Sequence[Cell]) -> dict[str, bool]:
    """Clé → publiée ? Les cellules masquées réunies passent le seuil (ou tout l'est)."""
    hidden = [c for c in cells if not _passes(c)]
    shown = sorted((c for c in cells if _passes(c)), key=_size)
    while hidden and shown and not _passes(merge(hidden)):
        hidden.append(shown.pop(0))
    hidden_keys = {c.key for c in hidden}
    return {c.key: c.key not in hidden_keys for c in cells}


def fold_cells(
    cells: Sequence[Cell], *, limit: int | None = None
) -> tuple[list[Cell], Cell | None]:
    """Cellules citées (par montant décroissant) et « autres » (None s'il n'y a rien à fondre)."""
    ordered = sorted(cells, key=lambda c: (-c.amount, -len(c.people), c.key))
    shown = [c for c in ordered if _passes(c)]
    if limit is not None:
        shown = shown[:limit]
    kept = {c.key for c in shown}
    rest = [c for c in ordered if c.key not in kept]
    while rest and shown and not _passes(merge(rest)):
        rest.append(shown.pop())
    return shown, (merge(rest) if rest else None)
