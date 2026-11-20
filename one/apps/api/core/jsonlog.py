"""Journalisation JSON structurée, sans donnée identifiante (AGENTS.md, conventions).

Règles :
- le message d'un enregistrement est un nom d'événement fixe (``http.request``), jamais une
  phrase interpolée avec des valeurs ;
- les champs passent par ``log_event`` et les clés identifiantes sont masquées ;
- une exception est journalisée par son type et sa pile, jamais par son message (un message
  d'erreur SQL peut contenir une valeur saisie : nom, téléphone…).
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

LOGGER_NAME: Final = "mulema"
MASK: Final = "[masqué]"

# Clés dont la valeur ne sort jamais dans un log (comparaison insensible à la casse).
IDENTIFYING_KEYS: Final = frozenset(
    {
        "name",
        "display_name",
        "given_name",
        "family_name",
        "full_name",
        "phone",
        "phone_e164",
        "email",
        "idp_subject",
        "subject",
        "token",
        "authorization",
        "password",
        "card_number",
        "qr_secret",
        "birth_date",
        "text",
        "motif",
        "medical_reason",
    }
)

_RESERVED: Final = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "fields",
}


type LogValue = str | int | float | bool | None


def _safe(key: str, value: object) -> LogValue:
    if key.lower() in IDENTIFYING_KEYS:
        return MASK
    if isinstance(value, UUID | datetime):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return MASK  # structure inconnue : on ne prend pas le risque de la sérialiser


class JsonFormatter(logging.Formatter):
    """Une ligne JSON par enregistrement : ``ts`` (UTC), ``level``, ``logger``, ``event``."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.msg if isinstance(record.msg, str) else MASK,
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            for key, value in fields.items():
                if key not in _RESERVED:
                    payload[key] = _safe(str(key), value)
        if record.exc_info and record.exc_info[0] is not None:
            exc_type, _, tb = record.exc_info
            # Cadres seulement (fichier, ligne, fonction) : ni message ni texte source, qui
            # peuvent porter une valeur littérale.
            payload["exception"] = {
                "type": exc_type.__qualname__,
                "stack": [f"{f.filename}:{f.lineno} {f.name}" for f in traceback.extract_tb(tb)],
            }
        return json.dumps(payload, ensure_ascii=False)


def log_event(logger: logging.Logger, level: int, event: str, **fields: object) -> None:
    """Journalise un événement nommé avec des champs pseudonymes."""
    logger.log(level, event, extra={"fields": fields})


def log_exception(logger: logging.Logger, event: str, **fields: object) -> None:
    """Comme ``log_event`` au niveau ERROR, avec le type et la pile de l'exception courante
    (à appeler dans un ``except``) ; jamais son message."""
    logger.error(event, exc_info=True, extra={"fields": fields})


def configure_json_logging(level: int = logging.INFO) -> None:
    """Installe le formateur JSON sur le logger ``mulema`` (idempotent)."""
    logger = logging.getLogger(LOGGER_NAME)
    if not any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
