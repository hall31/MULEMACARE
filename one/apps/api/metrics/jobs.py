"""Purge des événements d'usage expirés (rétention configurable), une organisation à la fois.

Sous ``mulema_app`` (RLS forcée) : la purge ne voit et ne supprime que les lignes de
l'organisation positionnée, dont l'échéance ``expires_at`` est passée à la fois pour l'horloge
de l'appelant ET pour celle de la base (``now()``) : une horloge fausse (ou un ``now`` mal
passé) ne supprime jamais une ligne encore conservée. Rejouable. Les agrégats ignorent déjà les
lignes expirées et les semaines où une purge a pu passer : la purge réduit le stockage, elle ne
change aucun résultat publié.

Planification (exploitation) — une fois par jour, par exemple à 03:00 heure de l'instance :

    cd apps && uv run python -m api.metrics purge --organization <uuid> [--organization <uuid> …]

Lit ``MULEMA_INSURANCE_DATABASE_URL`` et ``MULEMA_DB_APP_ROLE`` (``mulema_app`` par défaut) ;
refuse de tourner si la connexion échappe à la RLS. Code de sortie 0 si tout est purgé.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import CursorResult, text

from api.core.clock import SystemClock, ensure_utc
from api.core.database import Database
from api.core.jsonlog import LOGGER_NAME, log_event
from api.core.settings import DEFAULT_APP_ROLE

logger = logging.getLogger(f"{LOGGER_NAME}.metrics.jobs")

DATABASE_ENV = "MULEMA_INSURANCE_DATABASE_URL"
APP_ROLE_ENV = "MULEMA_DB_APP_ROLE"


async def purge_expired_events(database: Database, organization_id: UUID, now: datetime) -> int:
    now = ensure_utc(now)
    async with database.transaction(organization_id) as session:
        result = await session.execute(
            text(
                "DELETE FROM product_events WHERE organization_id = :org "
                "AND expires_at <= :now AND expires_at <= now()"
            ),
            {"org": organization_id, "now": now},
        )
    deleted = int(result.rowcount or 0) if isinstance(result, CursorResult) else 0
    log_event(
        logger,
        logging.INFO,
        "metrics.events_purged",
        organization_id=organization_id,
        deleted=deleted,
    )
    return deleted


async def purge_organizations(
    database: Database, organizations: Sequence[UUID], now: datetime
) -> dict[UUID, int]:
    await database.verify_isolation_enforced()
    return {org: await purge_expired_events(database, org, now) for org in organizations}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m api.metrics",
        description="Purge des événements d'usage expirés (mesure produit, P2).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    purge = commands.add_parser("purge", help="supprime les événements expirés")
    purge.add_argument(
        "--organization",
        action="append",
        required=True,
        type=UUID,
        help="organisation à purger (répétable)",
    )
    return parser


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    """Point d'entrée de la tâche planifiée ; ``env`` par défaut : l'environnement du processus."""
    args = _parser().parse_args(argv)
    environment = os.environ if env is None else env
    url = environment.get(DATABASE_ENV)
    if not url:
        msg = f"{DATABASE_ENV} manquante"
        raise RuntimeError(msg)
    role = environment.get(APP_ROLE_ENV, DEFAULT_APP_ROLE) or None

    async def run() -> dict[UUID, int]:
        database = Database(url, app_role=role, pool_size=1)
        try:
            return await purge_organizations(database, args.organization, SystemClock().now())
        finally:
            await database.dispose()

    asyncio.run(run())
    return 0
