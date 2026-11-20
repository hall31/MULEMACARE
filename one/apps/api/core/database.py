"""Accès à la base `insurance` : une transaction par requête, organisation positionnée.

Chaque transaction commence par :
- ``SET LOCAL ROLE mulema_app`` (rôle non propriétaire : la RLS forcée s'applique) ;
- ``SET LOCAL TIME ZONE 'UTC'`` (dates lues en UTC) ;
- ``set_config('app.organization_id', <org>, true)`` : équivalent paramétré de
  ``SET LOCAL app.organization_id``, lu par ``app_current_organization_id()`` du contrat.

Tout est local à la transaction : rien ne fuit d'une requête à l'autre via le pool. Sans
organisation, la RLS ne montre aucune ligne (échec fermé).

``autocommit_connection`` sert les services qui ouvrent et valident EUX-MÊMES leurs transactions
(grand livre L3 : le COMMIT, où la base contrôle l'équilibre, doit précéder la réponse). Même
pool, connexion psycopg en autocommit sous le rôle applicatif ; le service positionne
l'organisation (``SET LOCAL``) dans chacune de ses transactions.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final, cast
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.rows import TupleRow
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_ROLE_NAME: Final = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# Vrai si le rôle (``current_user`` ou ``session_user``) contourne la RLS : superutilisateur,
# BYPASSRLS, ou membre du propriétaire d'un objet du schéma public ou du schéma lui-même.
_PRIVILEGED: Final = text(
    """
    WITH who AS (
      SELECT r.oid, r.rolsuper, r.rolbypassrls FROM pg_roles r
      WHERE r.rolname = CASE CAST(:who AS text)
        WHEN 'session_user' THEN session_user ELSE current_user END
    )
    SELECT who.rolsuper OR who.rolbypassrls
      OR EXISTS (
        SELECT 1 FROM pg_class c
        WHERE c.relnamespace = 'public'::regnamespace
          AND pg_has_role(who.oid, c.relowner, 'MEMBER')
      )
      OR EXISTS (
        SELECT 1 FROM pg_namespace n
        WHERE n.nspname = 'public' AND pg_has_role(who.oid, n.nspowner, 'MEMBER')
      )
    FROM who
    """
)


class IsolationNotEnforcedError(RuntimeError):
    """Le rôle effectif contourne la RLS (superutilisateur ou BYPASSRLS) : démarrage refusé."""


class Database:
    def __init__(self, url: str, *, app_role: str | None, pool_size: int = 10) -> None:
        if app_role is not None and not _ROLE_NAME.fullmatch(app_role):
            msg = f"nom de rôle applicatif invalide : {app_role!r}"
            raise ValueError(msg)
        self._app_role = app_role
        options: dict[str, Any] = {"pool_pre_ping": True, "pool_size": pool_size}
        self._engine = create_async_engine(url, **options)
        self._sessions = async_sessionmaker(self._engine, expire_on_commit=False)

    @asynccontextmanager
    async def transaction(self, organization_id: UUID | None) -> AsyncIterator[AsyncSession]:
        """Ouvre une transaction : validée à la sortie normale, annulée sur exception."""
        async with self._sessions() as session, session.begin():
            if self._app_role is not None:
                # Identifiant validé par _ROLE_NAME : pas d'injection possible.
                await session.execute(text(f'SET LOCAL ROLE "{self._app_role}"'))
            await session.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            if organization_id is not None:
                await session.execute(
                    select(func.set_config("app.organization_id", str(organization_id), True))
                )
            yield session

    @asynccontextmanager
    async def autocommit_connection(self) -> AsyncIterator[psycopg.AsyncConnection[TupleRow]]:
        """Connexion du pool en autocommit, hors transaction, sous le rôle applicatif.

        Le rôle est posé pour la session (``SET ROLE``) puis retiré avant le retour au pool ; si
        le retrait échoue, la connexion est invalidée plutôt que rendue avec un état inconnu.
        """
        async with self._engine.connect() as pooled:
            await pooled.execution_options(isolation_level="AUTOCOMMIT")
            driver = (await pooled.get_raw_connection()).driver_connection
            if not isinstance(driver, psycopg.AsyncConnection) or not driver.autocommit:
                msg = "connexion psycopg en autocommit attendue"
                raise RuntimeError(msg)
            conn = cast("psycopg.AsyncConnection[TupleRow]", driver)
            if self._app_role is not None:
                await conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(self._app_role)))
            await conn.execute("SET TIME ZONE 'UTC'")
            try:
                yield conn
            finally:
                try:
                    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                        await conn.rollback()
                    await conn.execute("RESET ROLE")
                    await conn.execute("RESET TIME ZONE")
                except psycopg.Error:
                    await pooled.invalidate()
                    raise

    async def verify_isolation_enforced(self, *, strict_login: bool = False) -> None:
        """Échoue si le rôle effectif échappe à la RLS (échec fermé au démarrage).

        Refusé : superutilisateur, BYPASSRLS, ou membre du propriétaire d'une table, d'une
        séquence ou d'une vue du schéma ``public`` ou du schéma lui-même (un propriétaire peut
        désactiver la RLS ou supprimer une table). ``strict_login`` applique la même règle au
        rôle de CONNEXION (``session_user``), qui pourrait sinon quitter ``mulema_app`` par
        ``RESET ROLE`` (PRD ADR-007).
        """
        async with self.transaction(None) as session:
            effective = (await session.execute(_PRIVILEGED, {"who": "current_user"})).one()
            login = (await session.execute(_PRIVILEGED, {"who": "session_user"})).one()
        if effective[0]:
            msg = (
                "le rôle effectif de l'API contourne la RLS (superutilisateur, BYPASSRLS ou "
                "propriétaire) ; configurez un rôle applicatif non propriétaire "
                "(MULEMA_DB_APP_ROLE)"
            )
            raise IsolationNotEnforcedError(msg)
        if strict_login and login[0]:
            msg = (
                "le rôle de connexion de l'API est superutilisateur, BYPASSRLS ou propriétaire ; "
                "connectez-vous avec un rôle de connexion membre de mulema_app"
            )
            raise IsolationNotEnforcedError(msg)

    async def ping(self) -> None:
        """Requête triviale sous le rôle applicatif (vivacité de la base pour /readyz)."""
        async with self.transaction(None) as session:
            await session.execute(text("SELECT 1"))

    async def schema_revisions(self) -> frozenset[str]:
        """Révisions Alembic appliquées (``alembic_version``), lues sous le rôle applicatif.

        Exige ``GRANT SELECT ON alembic_version TO mulema_app`` (exploitation, CR-L10-02) ; sans
        ce droit, l'erreur remonte et /readyz répond « illisible »."""
        async with self.transaction(None) as session:
            rows = await session.execute(text("SELECT version_num FROM alembic_version"))
            values: list[object] = list(rows.scalars())
            return frozenset(str(value) for value in values)

    async def dispose(self) -> None:
        await self._engine.dispose()
