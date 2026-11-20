"""Horloge UTC. Les dates sont stockées et manipulées en UTC ; l'affichage local est côté web."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Horloge système, toujours conscient du fuseau et en UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Refuse une date naïve (sans fuseau) et convertit en UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        msg = "date sans fuseau horaire : toute date du noyau doit être en UTC"
        raise ValueError(msg)
    return value.astimezone(UTC)
