"""Choix de la version en vigueur à la date du soin (R3), pas à la date de traitement."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from api.rules.errors import NoVersionInForceError, OverlappingVersionsError
from api.rules.model import APPLICABLE_STATES, Period


class Versioned(Protocol):
    @property
    def version(self) -> int: ...

    @property
    def period(self) -> Period: ...

    @property
    def state(self) -> str: ...


def select_in_force[V: Versioned](versions: Iterable[V], at: date, *, what: str) -> V:
    """Unique version publiée couvrant ``at`` ; erreur à code stable sinon."""
    matches = sorted(
        (v for v in versions if v.state in APPLICABLE_STATES and v.period.contains(at)),
        key=lambda v: v.version,
    )
    if not matches:
        raise NoVersionInForceError(
            f"Aucune version de {what} n'est en vigueur au {at:%d/%m/%Y}.",
            "Publiez une version couvrant la date du soin, puis relancez l'évaluation.",
        )
    if len(matches) > 1:
        numbers = ", ".join(f"v{v.version}" for v in matches)
        raise OverlappingVersionsError(
            f"Plusieurs versions de {what} couvrent le {at:%d/%m/%Y} ({numbers}).",
            "Clôturez la version précédente avant de publier la nouvelle.",
        )
    return matches[0]
