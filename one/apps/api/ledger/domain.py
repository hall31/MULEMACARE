"""Domaine du grand livre (R7) : brouillons d'écriture, écritures validées, erreurs typées.

Montants en entiers FCFA (``int``, jamais ``float``), devise ``XOF`` explicite.
La base reste la barrière finale (triggers MCL01 à MCL04) ; ce module échoue tôt, avec un code
stable du contrat (specs/openapi.yaml, ``ErrorCode``) et un message en français qui dit quoi faire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final, Literal
from uuid import UUID

CURRENCY: Final = "XOF"

SourceType = Literal["prise_en_charge", "cotisation", "reglement", "contre_passation"]
AccountClass = Literal["actif", "passif", "charge", "produit"]
# Authentification et rôles : noyau L1 (``require_operation``), pas ce module.
ErrorCode = Literal["VAL-01", "NOT-01", "LED-01", "IDEM-01", "IDEM-02", "SYS-01"]

_HTTP_STATUS: Final[dict[str, int]] = {
    "VAL-01": 422,
    "NOT-01": 404,
    "LED-01": 409,
    "IDEM-01": 409,
    "IDEM-02": 409,
    "SYS-01": 500,
}


class LedgerError(Exception):
    """Erreur métier du grand livre, avec un code stable et une action pour l'utilisateur."""

    def __init__(self, code: ErrorCode, message: str, action: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code: ErrorCode = code
        self.message = message
        self.action = action

    @property
    def http_status(self) -> int:
        return _HTTP_STATUS[self.code]


def invalid(message: str, action: str = "Corrigez les données puis recommencez.") -> LedgerError:
    return LedgerError("VAL-01", message, action)


def not_found() -> LedgerError:
    return LedgerError(
        "NOT-01",
        "Cette écriture est introuvable.",
        "Vérifiez le numéro d'écriture dans le journal.",
    )


def already_reversed() -> LedgerError:
    return LedgerError(
        "LED-01",
        "Cette écriture a déjà été contre-passée.",
        "Consultez l'écriture de contre-passation liée.",
    )


@dataclass(frozen=True, slots=True)
class LineDraft:
    """Ligne à passer : exactement un des deux montants est strictement positif."""

    account_code: str
    debit_xof: int
    credit_xof: int
    provider_id: UUID | None = None
    member_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class EntryDraft:
    """Écriture à passer (hors contre-passation, qui a son propre chemin)."""

    accounting_date: date
    label: str
    source_type: SourceType
    lines: tuple[LineDraft, ...]
    source_id: UUID | None = None
    source_event_id: UUID | None = None
    reverses_entry_id: UUID | None = None


def validate_draft(draft: EntryDraft) -> None:
    """Refuse tôt ce que la base refuserait au COMMIT (MCL02) ou à l'insertion (CHECK)."""
    if not draft.label.strip():
        raise invalid("Le libellé de l'écriture est vide.")
    if len(draft.lines) < 2:  # noqa: PLR2004 — partie double : au moins deux lignes
        raise invalid("Une écriture a au moins deux lignes.")
    for line in draft.lines:
        for amount in (line.debit_xof, line.credit_xof):
            if type(amount) is not int or amount < 0:
                raise invalid("Les montants sont des entiers positifs en francs CFA.")
        if (line.debit_xof > 0) == (line.credit_xof > 0):
            raise invalid("Chaque ligne porte soit un débit, soit un crédit, strictement positif.")
    debit = sum(line.debit_xof for line in draft.lines)
    credit = sum(line.credit_xof for line in draft.lines)
    if debit != credit:
        raise invalid(
            f"Écriture déséquilibrée : débits {debit} FCFA, crédits {credit} FCFA.",
            "Ajustez les montants pour que les débits égalent les crédits.",
        )


@dataclass(frozen=True, slots=True)
class EntryQuery:
    """Filtres du journal (specs/openapi.yaml, listLedgerEntries)."""

    account_code: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    cursor: str | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class ReversalCommand:
    """Contre-passation demandée par un utilisateur, avec sa clé d'idempotence."""

    entry_id: UUID
    reason: str
    user_id: UUID
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class PostedLine:
    line_no: int
    account_code: str
    account_label: str
    debit_xof: int
    credit_xof: int
    provider_id: UUID | None
    member_id: UUID | None


@dataclass(frozen=True, slots=True)
class PostedEntry:
    id: UUID
    entry_number: str
    accounting_date: date
    posted_at: datetime
    label: str
    source_type: SourceType
    source_id: UUID | None
    source_event_id: UUID | None
    reverses_entry_id: UUID | None
    reversed_by_entry_id: UUID | None
    lines: tuple[PostedLine, ...]
    currency: str = CURRENCY

    @property
    def total_debit_xof(self) -> int:
        return sum(line.debit_xof for line in self.lines)

    @property
    def total_credit_xof(self) -> int:
        return sum(line.credit_xof for line in self.lines)


@dataclass(frozen=True, slots=True)
class EntryPage:
    items: list[PostedEntry]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class BalanceRow:
    account_code: str
    account_label: str
    debit_xof: int
    credit_xof: int


@dataclass(frozen=True, slots=True)
class Balance:
    """Totaux des mouvements débit / crédit par compte, écritures datées au plus tard ``at``."""

    at: date
    rows: list[BalanceRow] = field(default_factory=list)
    currency: str = CURRENCY

    @property
    def total_debit_xof(self) -> int:
        return sum(row.debit_xof for row in self.rows)

    @property
    def total_credit_xof(self) -> int:
        return sum(row.credit_xof for row in self.rows)
