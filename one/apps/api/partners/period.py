"""Période d'un agrégat : même fenêtre que la mesure produit (CR-P2-02, CR-P3-02).

Bornes demandées : jours civils locaux de l'organisation, inclus ; 30 derniers jours par défaut,
366 jours au plus, début avant fin ; sinon 422 VAL-01. La période PUBLIÉE est ensuite élargie
aux semaines civiles entières qu'elle touche (lundi → dimanche) et coupée à la dernière semaine
TERMINÉE (``api.metrics.windows.aligned_period``) : la semaine en cours et le futur ne sont
jamais publiés, et deux périodes publiées ne diffèrent que de semaines entières. Aucune semaine
terminée dans la période : 422 VAL-01 (champ ``to``). Renvoie aussi la fenêtre UTC
``[since, until)`` de la période publiée.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from api.core.errors import FieldError, ValidationFailedError
from api.metrics.windows import aligned_period, local_midnight, week_start

DEFAULT_PERIOD_DAYS: Final = 30
MAX_PERIOD_DAYS: Final = 366


@dataclass(frozen=True, slots=True)
class Period:
    start: date
    end: date
    since: datetime
    until: datetime


def _invalid(field: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(
        "La période demandée n'est pas valide.",
        "Choisissez une date de début avant la date de fin, sur un an au plus, "
        "et au moins une semaine (lundi à dimanche) déjà terminée.",
        errors=(FieldError(field, message),),
    )


def local_today(now: datetime, timezone: str) -> date:
    return now.astimezone(ZoneInfo(timezone)).date()


def published_until(now: datetime, timezone: str) -> datetime:
    """Fin de la dernière semaine terminée (lundi 00:00 local de la semaine en cours)."""
    zone = ZoneInfo(timezone)
    return local_midnight(week_start(local_today(now, timezone)), zone)


def resolve_period(start: date | None, end: date | None, now: datetime, timezone: str) -> Period:
    zone = ZoneInfo(timezone)
    today = local_today(now, timezone)
    period_to = end or today
    period_from = start or period_to - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    if period_from > period_to:
        raise _invalid("from", "La date de début dépasse la date de fin.")
    if (period_to - period_from).days + 1 > MAX_PERIOD_DAYS:
        raise _invalid("from", f"Période de {MAX_PERIOD_DAYS} jours au plus.")
    aligned = aligned_period(period_from, period_to, today)
    if aligned is None:
        raise _invalid(
            "to",
            "Aucune semaine terminée dans la période : les agrégats sont publiés par semaines "
            "entières (lundi à dimanche), une fois la semaine écoulée.",
        )
    first, last = aligned
    return Period(
        start=first,
        end=last,
        since=local_midnight(first, zone),
        until=local_midnight(last + timedelta(days=1), zone),
    )
