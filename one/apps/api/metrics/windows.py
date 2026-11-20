"""Fenêtres fixes de publication (CR-P2-02) : semaines civiles locales, lundi 00:00 → lundi suivant.

Contre le recoupement de deux requêtes (« la différence de deux périodes isole une
contribution ») :

- toute période publiée est élargie aux semaines ENTIÈRES qu'elle touche, puis coupée à la
  dernière semaine TERMINÉE : deux périodes publiées ne diffèrent que de semaines entières, et
  une semaine ne change plus une fois publiée (la semaine en cours n'est jamais publiée) ;
- en base, chaque indicateur remonte l'effectif de sa semaine la plus faible : une semaine non
  vide sous le seuil masque toute la période (``privacy``) ;
- événements d'usage : une semaine dont un événement a pu expirer (purge) n'est pas comptée, ni
  une semaine antérieure à la rotation de la clé de pseudonymisation (une personne y aurait deux
  empreintes et compterait deux fois).

Les semaines sont celles du fuseau de l'organisation (Africa/Abidjan, Africa/Dakar).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Final
from zoneinfo import ZoneInfo

WINDOW_DAYS: Final = 7


def week_start(day: date) -> date:
    """Lundi de la semaine civile de ``day``."""
    return day - timedelta(days=day.weekday())


def local_midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, zone)


def aligned_period(start: date, end: date, today: date) -> tuple[date, date] | None:
    """Du lundi de ``start`` au dimanche de ``end``, sans dépasser la dernière semaine terminée
    avant ``today`` ; ``None`` si aucune semaine terminée n'y reste."""
    first = week_start(start)
    last = min(
        week_start(end) + timedelta(days=WINDOW_DAYS - 1),
        week_start(today) - timedelta(days=1),
    )
    return (first, last) if last >= first else None


def retained_since(now: datetime, retention_days: int, zone: ZoneInfo) -> datetime:
    """Début de la première semaine dont AUCUN événement n'a pu expirer.

    Un événement posé à ``t`` expire à ``t + rétention`` : la semaine qui commence à ``w`` est
    intacte si ``w + rétention > now``. La semaine qui contient ``now - rétention`` commence au
    plus tard à cet instant : la suivante est la première intacte.
    """
    oldest = (now - timedelta(days=retention_days)).astimezone(zone).date()
    return local_midnight(week_start(oldest) + timedelta(days=WINDOW_DAYS), zone)


def key_floor(key_since: date | None, zone: ZoneInfo) -> datetime | None:
    """Premier lundi STRICTEMENT après le jour de rotation de la clé (``None`` : jamais tournée).

    Le jour de la rotation mêle les deux clés : sa semaine est écartée en entier.
    """
    if key_since is None:
        return None
    return local_midnight(week_start(key_since) + timedelta(days=WINDOW_DAYS), zone)


def event_floor(
    since: datetime,
    now: datetime,
    retention_days: int,
    key_since: date | None,
    zone: ZoneInfo,
) -> datetime:
    """Borne basse des événements d'usage comptés : début de période, semaines intactes, clé."""
    floors = [since, retained_since(now, retention_days, zone)]
    rotated = key_floor(key_since, zone)
    if rotated is not None:
        floors.append(rotated)
    return max(floors)
