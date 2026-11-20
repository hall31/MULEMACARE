"""Accès SQL du grand livre (psycopg 3 asynchrone). Ajout seul : INSERT et SELECT uniquement.

Toutes les fonctions supposent une transaction ouverte par le service, dans laquelle
``app.organization_id`` est positionné (RLS) et le verrou de journal est pris.

Défense en profondeur : chaque lecture filtre AUSSI ``organization_id`` explicitement, avec
l'organisation du principal. Si la RLS venait à manquer (rôle mal configuré, politique retirée),
aucune ligne d'une autre organisation ne serait lue (test_organization_filter.py).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

import psycopg
from psycopg.rows import TupleRow

from api.ledger.accounts import CHART_OF_ACCOUNTS, Account
from api.ledger.domain import (
    AccountClass,
    Balance,
    BalanceRow,
    EntryDraft,
    EntryQuery,
    PostedEntry,
    PostedLine,
    SourceType,
    invalid,
)

type Conn = psycopg.AsyncConnection[TupleRow]

ENTRY_NUMBER_PREFIX = "J"


async def set_organization(conn: Conn, organization_id: UUID) -> None:
    """Contexte RLS de la transaction courante (SET LOCAL)."""
    await conn.execute(
        "SELECT set_config('app.organization_id', %s, true)", (str(organization_id),)
    )


async def lock_journal(conn: Conn, organization_id: UUID) -> None:
    """Sérialise les écritures d'une organisation : numérotation continue, rejeu sans course."""
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (f"ledger:{organization_id}",)
    )


async def organization_timezone(conn: Conn, organization_id: UUID) -> str:
    cur = await conn.execute("SELECT timezone FROM organizations WHERE id = %s", (organization_id,))
    row = await cur.fetchone()
    if row is None:
        raise invalid("Organisation inconnue.", "Reconnectez-vous puis recommencez.")
    return str(row[0])


async def install_accounts(conn: Conn, organization_id: UUID) -> None:
    async with conn.cursor() as cur:
        await cur.executemany(
            "INSERT INTO ledger_accounts (organization_id, code, label, account_class) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (organization_id, code) DO NOTHING",
            [(organization_id, a.code, a.label, a.account_class) for a in CHART_OF_ACCOUNTS],
        )


async def list_accounts(conn: Conn, organization_id: UUID) -> list[Account]:
    cur = await conn.execute(
        "SELECT code, label, account_class FROM ledger_accounts WHERE organization_id = %s "
        "ORDER BY code",
        (organization_id,),
    )
    return [
        Account(str(code), str(label), cast("AccountClass", cls))
        for code, label, cls in await cur.fetchall()
    ]


async def account_ids(conn: Conn, organization_id: UUID, codes: Sequence[str]) -> dict[str, UUID]:
    cur = await conn.execute(
        "SELECT code, id FROM ledger_accounts WHERE organization_id = %s AND code = ANY(%s)",
        (organization_id, list(set(codes))),
    )
    return {str(code): cast("UUID", account_id) for code, account_id in await cur.fetchall()}


async def entry_id_for_event(conn: Conn, organization_id: UUID, event_id: UUID) -> UUID | None:
    cur = await conn.execute(
        "SELECT id FROM ledger_entries WHERE organization_id = %s AND source_event_id = %s",
        (organization_id, event_id),
    )
    row = await cur.fetchone()
    return None if row is None else cast("UUID", row[0])


async def reversal_of(conn: Conn, organization_id: UUID, entry_id: UUID) -> UUID | None:
    cur = await conn.execute(
        "SELECT id FROM ledger_entries WHERE organization_id = %s AND reverses_entry_id = %s",
        (organization_id, entry_id),
    )
    row = await cur.fetchone()
    return None if row is None else cast("UUID", row[0])


async def next_entry_number(conn: Conn, organization_id: UUID, accounting_date: date) -> str:
    """Numéro continu par exercice civil : J-AAAA-NNNNNNN (sous le verrou de journal)."""
    prefix = f"{ENTRY_NUMBER_PREFIX}-{accounting_date.year:04d}-"
    cur = await conn.execute(
        "SELECT coalesce(max(substring(entry_number FROM %s)::bigint), 0) + 1 "
        "FROM ledger_entries WHERE organization_id = %s AND entry_number ~ %s",
        (len(prefix) + 1, organization_id, f"^{prefix}[0-9]+$"),
    )
    row = await cur.fetchone()
    if row is None:  # un agrégat renvoie toujours une ligne
        raise RuntimeError("numérotation du journal : aucune ligne renvoyée")
    return f"{prefix}{int(row[0]):07d}"


async def insert_entry_unchecked(
    conn: Conn,
    organization_id: UUID,
    draft: EntryDraft,
    entry_number: str,
    *,
    created_by: UUID | None = None,
) -> UUID:
    """Insère l'écriture et ses lignes SANS contrôle applicatif (la base contrôle au COMMIT).

    Réservé au service après ``validate_draft`` ; exposé pour prouver que la base refuse seule
    une écriture déséquilibrée.
    """
    ids = await account_ids(conn, organization_id, [line.account_code for line in draft.lines])
    unknown = sorted({line.account_code for line in draft.lines} - ids.keys())
    if unknown:
        raise invalid(
            f"Compte inconnu du plan de comptes : {', '.join(unknown)}.",
            "Choisissez un compte du plan de comptes de l'organisation.",
        )
    cur = await conn.execute(
        "INSERT INTO ledger_entries (organization_id, entry_number, accounting_date, label, "
        "source_type, source_id, source_event_id, reverses_entry_id, created_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            organization_id,
            entry_number,
            draft.accounting_date,
            draft.label,
            draft.source_type,
            draft.source_id,
            draft.source_event_id,
            draft.reverses_entry_id,
            created_by,
        ),
    )
    row = await cur.fetchone()
    if row is None:  # INSERT … RETURNING renvoie toujours la ligne insérée
        raise RuntimeError("insertion d'écriture sans identifiant renvoyé")
    entry_id = cast("UUID", row[0])
    async with conn.cursor() as lines_cur:
        await lines_cur.executemany(
            "INSERT INTO ledger_lines (organization_id, entry_id, line_no, account_id, "
            "debit_xof, credit_xof, provider_id, member_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    organization_id,
                    entry_id,
                    line_no,
                    ids[line.account_code],
                    line.debit_xof,
                    line.credit_xof,
                    line.provider_id,
                    line.member_id,
                )
                for line_no, line in enumerate(draft.lines, start=1)
            ],
        )
    return entry_id


_ENTRY_COLUMNS = (
    "e.id, e.entry_number, e.accounting_date, e.posted_at, e.label, e.source_type, e.source_id, "
    "e.source_event_id, e.reverses_entry_id, "
    "(SELECT r.id FROM ledger_entries r WHERE r.organization_id = e.organization_id "
    " AND r.reverses_entry_id = e.id) AS reversed_by"
)


async def _load_lines(
    conn: Conn, organization_id: UUID, entry_ids: list[UUID]
) -> dict[UUID, list[PostedLine]]:
    out: dict[UUID, list[PostedLine]] = {entry_id: [] for entry_id in entry_ids}
    if not entry_ids:
        return out
    cur = await conn.execute(
        "SELECT l.entry_id, l.line_no, a.code, a.label, l.debit_xof, l.credit_xof, "
        "l.provider_id, l.member_id FROM ledger_lines l "
        "JOIN ledger_accounts a ON a.organization_id = l.organization_id AND a.id = l.account_id "
        "WHERE l.organization_id = %s AND l.entry_id = ANY(%s) ORDER BY l.entry_id, l.line_no",
        (organization_id, entry_ids),
    )
    for entry_id, line_no, code, label, debit, credit, provider, member in await cur.fetchall():
        out[cast("UUID", entry_id)].append(
            PostedLine(
                line_no=int(line_no),
                account_code=str(code),
                account_label=str(label),
                debit_xof=int(debit),
                credit_xof=int(credit),
                provider_id=cast("UUID | None", provider),
                member_id=cast("UUID | None", member),
            )
        )
    return out


def _entry(row: TupleRow, lines: list[PostedLine]) -> PostedEntry:
    return PostedEntry(
        id=cast("UUID", row[0]),
        entry_number=str(row[1]),
        accounting_date=cast("date", row[2]),
        posted_at=cast("datetime", row[3]),
        label=str(row[4]),
        source_type=cast("SourceType", row[5]),
        source_id=cast("UUID | None", row[6]),
        source_event_id=cast("UUID | None", row[7]),
        reverses_entry_id=cast("UUID | None", row[8]),
        reversed_by_entry_id=cast("UUID | None", row[9]),
        lines=tuple(lines),
    )


async def load_entry(conn: Conn, organization_id: UUID, entry_id: UUID) -> PostedEntry | None:
    cur = await conn.execute(
        f"SELECT {_ENTRY_COLUMNS} FROM ledger_entries e "  # noqa: S608 — colonnes constantes
        "WHERE e.organization_id = %s AND e.id = %s",
        (organization_id, entry_id),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    lines = await _load_lines(conn, organization_id, [entry_id])
    return _entry(row, lines[entry_id])


async def page_entries(
    conn: Conn, organization_id: UUID, query: EntryQuery, after: tuple[datetime, str] | None
) -> tuple[list[PostedEntry], tuple[datetime, str] | None]:
    """Écritures les plus récentes d'abord ; pagination par clé (posted_at, entry_number)."""
    conditions: list[str] = ["e.organization_id = %s"]
    params: list[Any] = [organization_id]
    if query.account_code is not None:
        conditions.append(
            "EXISTS (SELECT 1 FROM ledger_lines l JOIN ledger_accounts a "
            "ON a.organization_id = l.organization_id AND a.id = l.account_id "
            "WHERE l.organization_id = e.organization_id AND l.entry_id = e.id AND a.code = %s)"
        )
        params.append(query.account_code)
    if query.date_from is not None:
        conditions.append("e.accounting_date >= %s")
        params.append(query.date_from)
    if query.date_to is not None:
        conditions.append("e.accounting_date <= %s")
        params.append(query.date_to)
    if after is not None:
        conditions.append("(e.posted_at, e.entry_number) < (%s, %s)")
        params.extend(after)
    where = f"WHERE {' AND '.join(conditions)}"
    cur = await conn.execute(
        f"SELECT {_ENTRY_COLUMNS} FROM ledger_entries e {where} "  # noqa: S608 — fragments constants
        "ORDER BY e.posted_at DESC, e.entry_number DESC LIMIT %s",
        (*params, query.limit + 1),
    )
    rows = await cur.fetchall()
    has_more = len(rows) > query.limit
    rows = rows[: query.limit]
    lines = await _load_lines(conn, organization_id, [cast("UUID", row[0]) for row in rows])
    entries = [_entry(row, lines[cast("UUID", row[0])]) for row in rows]
    last = entries[-1] if has_more and entries else None
    return entries, (None if last is None else (last.posted_at, last.entry_number))


async def balance_at(conn: Conn, organization_id: UUID, at: date) -> Balance:
    """Totaux des mouvements par compte (tous les comptes du plan, même sans mouvement)."""
    cur = await conn.execute(
        "SELECT a.code, a.label, coalesce(sum(l.debit_xof), 0), coalesce(sum(l.credit_xof), 0) "
        "FROM ledger_accounts a "
        "LEFT JOIN (ledger_lines l JOIN ledger_entries e "
        "           ON e.organization_id = l.organization_id AND e.id = l.entry_id "
        "           AND e.accounting_date <= %s) "
        "  ON l.organization_id = a.organization_id AND l.account_id = a.id "
        "WHERE a.organization_id = %s "
        "GROUP BY a.code, a.label ORDER BY a.code",
        (at, organization_id),
    )
    rows = [
        BalanceRow(str(code), str(label), int(debit), int(credit))
        for code, label, debit, credit in await cur.fetchall()
    ]
    return Balance(at=at, rows=rows)


async def emit_entry_posted(conn: Conn, organization_id: UUID, entry: PostedEntry) -> None:
    """``ledger.entry_posted`` (specs/events.md) dans la transaction de l'écriture."""
    payload = {
        "entry_id": str(entry.id),
        "entry_number": entry.entry_number,
        "accounting_date": entry.accounting_date.isoformat(),
        "source_type": entry.source_type,
        "source_id": _opt(entry.source_id),
        "source_event_id": _opt(entry.source_event_id),
        "reverses_entry_id": _opt(entry.reverses_entry_id),
        "currency": entry.currency,
        "total_debit_xof": entry.total_debit_xof,
        "total_credit_xof": entry.total_credit_xof,
        "lines": [
            {
                "line_no": line.line_no,
                "account_code": line.account_code,
                "debit_xof": line.debit_xof,
                "credit_xof": line.credit_xof,
                "provider_id": _opt(line.provider_id),
                "member_id": _opt(line.member_id),
            }
            for line in entry.lines
        ],
    }
    await conn.execute(
        "INSERT INTO outbox_events (organization_id, event_type, event_version, aggregate_id, "
        "payload) VALUES (%s, 'ledger.entry_posted', 1, %s, %s)",
        (organization_id, entry.id, json.dumps(payload)),
    )


def _opt(value: UUID | None) -> str | None:
    return None if value is None else str(value)


async def pending_events(conn: Conn, organization_id: UUID, limit: int) -> list[TupleRow]:
    """Événements consommables sans écriture correspondante (anti-jointure, sans marquage).

    L'outbox est partagée : ``published_at`` appartient au publieur, pas à ce consommateur.
    Les décisions sans accord et les montants nuls ne passent jamais d'écriture : exclus.
    Une charge utile malformée n'est PAS exclue : le consommateur la signale à chaque passage.
    """
    cur = await conn.execute(
        "SELECT o.id, o.organization_id, o.event_type, o.event_version, o.occurred_at, o.payload "
        "FROM outbox_events o "
        "WHERE o.organization_id = %s "
        "AND o.event_type IN ('claim.decided', 'contribution.received') "
        "AND NOT EXISTS (SELECT 1 FROM ledger_entries e "
        "                WHERE e.organization_id = o.organization_id "
        "                AND e.source_event_id = o.id) "
        "AND NOT coalesce(o.event_type = 'claim.decided' AND ("
        "     o.payload->>'outcome' IN ('en_revue', 'refusee', 'pieces_demandees', 'annulee') "
        "     OR o.payload->'covered_xof' = '0'::jsonb), false) "
        "AND NOT coalesce(o.event_type = 'contribution.received' "
        "         AND o.payload->'amount_xof' = '0'::jsonb, false) "
        "ORDER BY o.occurred_at, o.id LIMIT %s",
        (organization_id, limit),
    )
    return await cur.fetchall()
