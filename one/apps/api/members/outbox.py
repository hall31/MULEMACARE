"""Écriture des événements L4 dans ``outbox_events`` (specs/events.md).

L'événement est inséré dans la MÊME transaction que le changement d'état qui le cause. L'outbox
est partagée : ce module n'écrit jamais ``published_at`` (ni L3, qui consomme sans marquer).
Les payloads ne portent que des identifiants pseudonymes, des montants entiers et des codes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import ensure_utc

type L4Event = Literal["member.status_changed", "contribution.received"]

EVENT_VERSION: Final = 1


def rfc3339(moment: datetime) -> str:
    """Horodatage UTC au format RFC 3339 avec ``Z``."""
    return ensure_utc(moment).astimezone(UTC).isoformat().replace("+00:00", "Z")


def iso_date(day: date) -> str:
    return day.isoformat()


@dataclass(frozen=True, slots=True)
class NewEvent:
    organization_id: UUID
    event_type: L4Event
    aggregate_id: UUID
    payload: dict[str, Any]
    occurred_at: datetime


async def emit(session: AsyncSession, event: NewEvent) -> UUID:
    """Ajoute l'événement à la boîte d'envoi ; renvoie son ``event_id``."""
    row = (
        await session.execute(
            text(
                "INSERT INTO outbox_events (organization_id, event_type, event_version, "
                "aggregate_id, payload, occurred_at) "
                "VALUES (:org, :type, :version, :aggregate, CAST(:payload AS jsonb), :at) "
                "RETURNING id"
            ),
            {
                "org": event.organization_id,
                "type": event.event_type,
                "version": EVENT_VERSION,
                "aggregate": event.aggregate_id,
                "payload": json.dumps(event.payload),
                "at": ensure_utc(event.occurred_at),
            },
        )
    ).one()
    event_id: UUID = row[0]
    return event_id
