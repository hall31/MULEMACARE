"""Normalisation stricte des valeurs de la source (fonctions pures).

Règle unique : une valeur qui ne se normalise pas EXACTEMENT est rejetée avec un motif
(``RowRejectedError``), jamais arrondie, tronquée ou remplacée par un défaut. Les montants
deviennent des entiers en francs CFA (ADR-005) : ``12500.00`` → 12 500 ; ``12500.50`` → rejet
(le franc CFA n'a pas de centimes : arrondir serait inventer de l'argent). Un flottant n'est
jamais accepté comme montant.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Final

from api.legacy_import.errors import RowRejectedError

_DECIMAL: Final = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
_DATE: Final = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})(?:[ T][0-9]{2}:[0-9]{2}(:[0-9]{2})?)?$")
_E164: Final = re.compile(r"^\+[1-9][0-9]{7,14}$")
_BP_PER_PERCENT: Final = 100
_MAX_BP: Final = 10_000
_TRUE: Final = frozenset({"1", "true", "vrai", "oui", "yes"})
_FALSE: Final = frozenset({"0", "false", "faux", "non", "no"})


def text_or_none(raw: object) -> str | None:
    """Texte nettoyé (espaces de bord) ; vide ou NULL → None."""
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    value = str(raw).strip()
    return value or None


def required_text(raw: object, field: str) -> str:
    value = text_or_none(raw)
    if value is None:
        raise RowRejectedError("REJ-03", field)
    return value


def _decimal(raw: object, field: str, code: str) -> Decimal:
    if isinstance(raw, bool) or isinstance(raw, float):
        raise RowRejectedError(code, field)
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, Decimal):
        if not raw.is_finite():
            raise RowRejectedError(code, field)
        return raw
    value = text_or_none(raw)
    if value is None:
        raise RowRejectedError("REJ-03", field)
    if not _DECIMAL.fullmatch(value):
        raise RowRejectedError(code, field)
    try:
        return Decimal(value)
    except InvalidOperation:
        raise RowRejectedError(code, field) from None


def to_decimal(raw: object, field: str) -> Decimal:
    """Nombre décimal exact (jamais un flottant)."""
    return _decimal(raw, field, "REJ-05")


def to_xof(raw: object, field: str) -> int:
    """Montant décimal de la source → entier en francs CFA, exact et positif ou nul."""
    amount = _decimal(raw, field, "REJ-02")
    if amount < 0 or amount != amount.to_integral_value():
        raise RowRejectedError("REJ-02", field)
    return int(amount)


def to_int(raw: object, field: str, *, minimum: int = 0) -> int:
    value = _decimal(raw, field, "REJ-05")
    if value != value.to_integral_value() or value < minimum:
        raise RowRejectedError("REJ-05", field)
    return int(value)


def percent_to_bp(raw: object, field: str) -> int:
    """Taux en pourcentage (``80.00``) → points de base (8000), exact, entre 0 et 10 000."""
    bp = _decimal(raw, field, "REJ-09") * _BP_PER_PERCENT
    if bp != bp.to_integral_value() or not 0 <= bp <= _MAX_BP:
        raise RowRejectedError("REJ-09", field)
    return int(bp)


def to_date(raw: object, field: str) -> date:
    """Date civile ; une date-heure garde son jour (aucun fuseau supposé, rien d'autre)."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    value = required_text(raw, field)
    match = _DATE.fullmatch(value)
    if match is None:
        raise RowRejectedError("REJ-05", field)
    try:
        return date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:  # 0000-00-00, 2026-02-30…
        raise RowRejectedError("REJ-05", field) from None


def to_optional_date(raw: object, field: str) -> date | None:
    if text_or_none(raw) is None and not isinstance(raw, date):
        return None
    return to_date(raw, field)


def to_bool(raw: object, field: str) -> bool:
    if isinstance(raw, bool):
        return raw
    value = required_text(raw, field).lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise RowRejectedError("REJ-05", field)


def _ascii(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def to_code(raw: object, field: str, pattern: re.Pattern[str]) -> str:
    """Code en majuscules ASCII (``Famille Or`` → ``FAMILLE-OR``) qui doit respecter ``pattern``."""
    value = _ascii(required_text(raw, field)).upper()
    code = re.sub(r"[^A-Z0-9]+", "-", value).strip("-")
    if not pattern.fullmatch(code):
        raise RowRejectedError("REJ-05", field)
    return code


def to_category(raw: object, field: str) -> str:
    """Catégorie de garantie (``Soins courants`` → ``soins_courants``), ``^[a-z_]{2,40}$``."""
    value = _ascii(required_text(raw, field)).lower()
    category = re.sub(r"[^a-z]+", "_", value).strip("_")
    if not re.fullmatch(r"[a-z_]{2,40}", category):
        raise RowRejectedError("REJ-05", field)
    return category


def normalize_email(raw: object) -> str | None:
    """Adresse normalisée pour le SEUL dédoublonnage en mémoire : jamais stockée, jamais clé."""
    value = text_or_none(raw)
    if value is None:
        return None
    email = unicodedata.normalize("NFKC", value).strip().lower()
    local, at, domain = email.partition("@")
    if not at or not local or "." not in domain or "@" in domain:
        return None
    return email


def to_e164(raw: object, country_code: object = None) -> str | None:
    """Téléphone au format E.164 ; None si absent OU non normalisable (signalé par l'appelant).

    ``country_code`` : indicatif déclaré par la source (``225`` ou ``+225``), jamais deviné.
    """
    value = text_or_none(raw)
    if value is None:
        return None
    digits = re.sub(r"[^0-9+]", "", value)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+"):
        prefix = re.sub(r"[^0-9]", "", text_or_none(country_code) or "")
        if not prefix:
            return None
        digits = f"+{prefix}{digits.lstrip('0')}"
    return digits if _E164.fullmatch(digits) else None


def in_vocabulary(raw: object, field: str, vocabulary: dict[str, str]) -> str:
    """Valeur traduite par un vocabulaire DÉCLARÉ ; inconnue → rejet (REJ-06)."""
    value = required_text(raw, field)
    if value not in vocabulary:
        raise RowRejectedError("REJ-06", field)
    return vocabulary[value]
