"""Service du grand livre (R7) : passer, contre-passer, lire le journal, la balance.

Chaque opération ouvre SA transaction (la connexion doit être en autocommit) : le COMMIT, où la
base vérifie l'équilibre (MCL02) et le miroir de la contre-passation (MCL04), a lieu avant le
retour de la fonction, donc avant toute réponse HTTP. L'organisation est positionnée en
``SET LOCAL`` dans chaque transaction (RLS), à partir du principal authentifié uniquement.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg

from api.core.jsonlog import LOGGER_NAME, log_event
from api.ledger import idempotency, repository
from api.ledger.accounts import Account
from api.ledger.domain import (
    Balance,
    EntryDraft,
    EntryPage,
    EntryQuery,
    LineDraft,
    PostedEntry,
    ReversalCommand,
    already_reversed,
    invalid,
    not_found,
    validate_draft,
)
from api.ledger.repository import Conn

logger = logging.getLogger(f"{LOGGER_NAME}.ledger.service")

REVERSAL_SCOPE: Final = "command:ledger.reverse"
MAX_PAGE: Final = 200
_REASON_MIN, _REASON_MAX = 3, 200
_KEY_MIN, _KEY_MAX = 8, 200


@asynccontextmanager
async def unit_of_work(conn: Conn, organization_id: UUID, *, lock: bool) -> AsyncIterator[None]:
    """Transaction réelle (pas un point de sauvegarde), organisation positionnée, erreurs typées."""
    if not conn.autocommit or conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        raise RuntimeError(
            "Le grand livre exige une connexion en autocommit, hors transaction : sinon le "
            "COMMIT (contrôle d'équilibre) aurait lieu après la réponse."
        )
    try:
        async with conn.transaction():
            await repository.set_organization(conn, organization_id)
            if lock:
                await repository.lock_journal(conn, organization_id)
            yield
    except psycopg.Error as exc:
        mapped = _map_database_error(exc)
        if mapped is None:
            raise
        log_event(
            logger,
            logging.WARNING,
            "ledger.database_refusal",
            sqlstate=exc.sqlstate,
            organization_id=organization_id,
        )
        raise mapped from exc


def _map_database_error(exc: psycopg.Error) -> Exception | None:
    if exc.sqlstate in {"MCL02", "MCL04", "23514"}:
        return invalid(
            "La base a refusé une écriture incohérente (équilibre ou contre-passation).",
            "Vérifiez les montants et les comptes, puis recommencez.",
        )
    constraint = exc.diag.constraint_name or ""
    if exc.sqlstate == "23505" and "reverses_entry_id" in constraint:
        return already_reversed()
    return None


async def _local_today(conn: Conn, organization_id: UUID) -> date:
    timezone = await repository.organization_timezone(conn, organization_id)
    return datetime.now(ZoneInfo(timezone)).date()


async def post_locked(
    conn: Conn, organization_id: UUID, draft: EntryDraft, *, created_by: UUID | None = None
) -> PostedEntry:
    """Passe une écriture validée ; à appeler dans ``unit_of_work(lock=True)``."""
    validate_draft(draft)
    number = await repository.next_entry_number(conn, organization_id, draft.accounting_date)
    entry_id = await repository.insert_entry_unchecked(
        conn, organization_id, draft, number, created_by=created_by
    )
    entry = await repository.load_entry(conn, organization_id, entry_id)
    if entry is None:  # vient d'être insérée dans cette transaction
        raise RuntimeError("écriture insérée introuvable dans sa propre transaction")
    await repository.emit_entry_posted(conn, organization_id, entry)
    log_event(
        logger,
        logging.INFO,
        "ledger.entry_posted",
        organization_id=organization_id,
        entry_id=entry.id,
        entry_number=entry.entry_number,
        source_type=entry.source_type,
    )
    return entry


async def post_entry(
    conn: Conn, organization_id: UUID, draft: EntryDraft, *, created_by: UUID | None = None
) -> PostedEntry:
    """Passe une écriture en partie double (débits = crédits, au moins deux lignes)."""
    if draft.source_type == "contre_passation" or draft.reverses_entry_id is not None:
        raise invalid(
            "Une contre-passation ne se saisit pas comme une écriture ordinaire.",
            "Utilisez la contre-passation depuis l'écriture d'origine.",
        )
    validate_draft(draft)
    async with unit_of_work(conn, organization_id, lock=True):
        entry = await post_locked(conn, organization_id, draft, created_by=created_by)
    return entry


def _reversal_request_hash(entry_id: UUID, reason: str) -> str:
    body = json.dumps({"entry_id": str(entry_id), "reason": reason}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


async def reverse_entry(conn: Conn, organization_id: UUID, command: ReversalCommand) -> PostedEntry:
    """Contre-passe une écriture : miroir exact (débits et crédits inversés), une seule fois.

    Idempotent sur ``idempotency_key`` : même clé et même corps renvoient la même écriture ;
    même clé et autre corps donnent IDEM-01. Une seconde contre-passation donne LED-01.
    """
    entry_id, key = command.entry_id, command.idempotency_key
    reason = command.reason.strip()
    if not _REASON_MIN <= len(reason) <= _REASON_MAX:
        raise invalid("Le motif de contre-passation fait de 3 à 200 caractères.")
    if not _KEY_MIN <= len(key) <= _KEY_MAX:
        raise invalid("La clé d'idempotence fait de 8 à 200 caractères.")
    request_hash = _reversal_request_hash(entry_id, reason)
    async with unit_of_work(conn, organization_id, lock=True):
        replayed = await idempotency.begin(conn, organization_id, REVERSAL_SCOPE, key, request_hash)
        if replayed is not None:
            previous = await repository.load_entry(conn, organization_id, replayed)
            if previous is None:  # le grand livre est en ajout seul
                raise RuntimeError("écriture d'une clé d'idempotence introuvable")
            return previous  # la transaction ne contient que des lectures
        original = await repository.load_entry(conn, organization_id, entry_id)
        if original is None:
            raise not_found()
        if original.reversed_by_entry_id is not None:
            raise already_reversed()
        draft = EntryDraft(
            accounting_date=await _local_today(conn, organization_id),
            label=f"Contre-passation {original.entry_number} : {reason}",
            source_type="contre_passation",
            source_id=original.source_id,
            reverses_entry_id=original.id,
            lines=tuple(
                LineDraft(
                    account_code=line.account_code,
                    debit_xof=line.credit_xof,
                    credit_xof=line.debit_xof,
                    provider_id=line.provider_id,
                    member_id=line.member_id,
                )
                for line in original.lines
            ),
        )
        reversal = await post_locked(conn, organization_id, draft, created_by=command.user_id)
        await idempotency.complete(conn, organization_id, REVERSAL_SCOPE, key, reversal.id)
    return reversal


async def get_entry(conn: Conn, organization_id: UUID, entry_id: UUID) -> PostedEntry:
    async with unit_of_work(conn, organization_id, lock=False):
        entry = await repository.load_entry(conn, organization_id, entry_id)
    if entry is None:
        raise not_found()
    return entry


def _encode_cursor(key: tuple[datetime, str]) -> str:
    raw = json.dumps([key[0].isoformat(), key[1]]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        posted_at, number = json.loads(base64.urlsafe_b64decode(padded.encode()))
        parsed = datetime.fromisoformat(posted_at)
    except (binascii.Error, ValueError, TypeError, UnicodeDecodeError) as exc:
        raise invalid(
            "Le curseur de pagination est invalide.", "Recommencez depuis la première page."
        ) from exc
    if not isinstance(number, str) or parsed.tzinfo is None:
        raise invalid(
            "Le curseur de pagination est invalide.", "Recommencez depuis la première page."
        )
    return parsed, number


async def list_entries(
    conn: Conn, organization_id: UUID, query: EntryQuery | None = None
) -> EntryPage:
    """Journal, écritures les plus récentes d'abord, avec leurs lignes."""
    query = query or EntryQuery()
    if not 1 <= query.limit <= MAX_PAGE:
        raise invalid("La taille de page va de 1 à 200.")
    after = None if query.cursor is None else _decode_cursor(query.cursor)
    async with unit_of_work(conn, organization_id, lock=False):
        entries, next_key = await repository.page_entries(conn, organization_id, query, after)
    return EntryPage(entries, None if next_key is None else _encode_cursor(next_key))


async def balance(conn: Conn, organization_id: UUID, *, at: date | None = None) -> Balance:
    """Balance à une date (par défaut : aujourd'hui, heure locale de l'organisation)."""
    async with unit_of_work(conn, organization_id, lock=False):
        day = at if at is not None else await _local_today(conn, organization_id)
        result = await repository.balance_at(conn, organization_id, day)
    return result


async def list_accounts(conn: Conn, organization_id: UUID) -> list[Account]:
    async with unit_of_work(conn, organization_id, lock=False):
        accounts = await repository.list_accounts(conn, organization_id)
    return accounts


async def install_chart_of_accounts(conn: Conn, organization_id: UUID) -> None:
    """Installe le plan de comptes initial (idempotent : comptes existants conservés)."""
    async with unit_of_work(conn, organization_id, lock=False):
        await repository.install_accounts(conn, organization_id)
