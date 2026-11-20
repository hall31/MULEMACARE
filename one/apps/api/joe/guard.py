"""Garde de lecture seule : les outils de JOE s'exécutent dans un point de sauvegarde que la
BASE tient en lecture seule, avec un contrôle applicatif en plus.

``read_only(session)`` :
1. ouvre un point de sauvegarde et pose ``SET LOCAL transaction_read_only = on`` : PostgreSQL
   refuse alors toute écriture (INSERT, UPDATE, DELETE, ``nextval``, CTE d'écriture…) ;
2. enregistre chaque requête SQL émise sur la connexion et refuse AVANT exécution ce qui ne
   commence pas par ``SELECT``, ``WITH`` ou ``SHOW`` (``ReadOnlyViolationError``) ;
3. à la sortie, annule le point de sauvegarde : la lecture seule disparaît avec lui (retour
   au mode lecture-écriture prouvé par test), et rien de ce que l'outil aurait pu laisser ne
   subsiste. Le journal ``ai_actions`` s'écrit ensuite, hors du garde.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Final

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

_READ: Final = re.compile(r"^\s*(SELECT|WITH|SHOW)\b", re.IGNORECASE)


class ReadOnlyViolationError(RuntimeError):
    """Un outil de JOE a tenté une écriture (refusée avant d'atteindre la base)."""


@dataclass
class ReadOnlyScope:
    """Preuve qu'on est dans le garde, et liste des requêtes émises."""

    statements: list[str] = field(default_factory=list)
    active: bool = True


@asynccontextmanager
async def read_only(session: AsyncSession) -> AsyncIterator[ReadOnlyScope]:
    scope = ReadOnlyScope()
    savepoint = await session.begin_nested()
    connection = await session.connection()
    sync_connection = connection.sync_connection
    if sync_connection is None:  # pragma: no cover — connexion toujours ouverte ici
        msg = "connexion synchrone introuvable"
        raise RuntimeError(msg)

    def inspect_statement(  # noqa: PLR0913, PLR0917 — signature imposée par SQLAlchemy
        conn: Connection,
        cursor: object,
        statement: str,
        parameters: Sequence[Any] | dict[str, Any] | None,
        context: object,
        executemany: bool,
    ) -> None:
        del conn, cursor, parameters, context, executemany
        if not _READ.match(statement):
            raise ReadOnlyViolationError(statement.split(None, 1)[0].upper())
        scope.statements.append(statement)

    try:
        await session.execute(text("SET LOCAL transaction_read_only = on"))
        event.listen(sync_connection, "before_cursor_execute", inspect_statement)
        try:
            yield scope
        finally:
            event.remove(sync_connection, "before_cursor_execute", inspect_statement)
    finally:
        scope.active = False
        if savepoint.is_active:
            await savepoint.rollback()
