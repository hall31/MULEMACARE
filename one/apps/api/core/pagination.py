"""Curseurs de pagination opaques (``cursor`` du contrat) : position (horodatage, id)."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from uuid import UUID

from api.core.clock import ensure_utc
from api.core.errors import FieldError, ValidationFailedError
from api.core.repositories import Keyset


def encode_cursor(position: Keyset | None) -> str | None:
    if position is None:
        return None
    raw = json.dumps({"t": ensure_utc(position.at).isoformat(), "i": str(position.id)})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> Keyset | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        return Keyset(at=ensure_utc(datetime.fromisoformat(data["t"])), id=UUID(data["i"]))
    except (ValueError, KeyError, TypeError, binascii.Error) as exc:
        raise ValidationFailedError(
            "Le curseur de pagination n'est pas valide.",
            "Rechargez la liste depuis le début.",
            errors=(FieldError("cursor", "Curseur inconnu ou altéré."),),
        ) from exc
