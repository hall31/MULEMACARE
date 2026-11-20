"""Connexion en autocommit du noyau, pour les services qui valident eux-mêmes (grand livre L3).

Le service ouvre SA transaction et la valide avant de rendre la main : la connexion doit être en
autocommit, hors transaction, sous le rôle applicatif (RLS appliquée), et revenir au pool sans
rien laisser derrière elle (ni rôle, ni autocommit).
"""

from __future__ import annotations

import asyncio

import psycopg
from sqlalchemy import text

from api.core.database import Database
from api.core.tests.conftest import APP_ROLE, CoreSeed


def test_connexion_autocommit_sous_role_applicatif_et_pool_propre(core_seed: CoreSeed) -> None:
    async def scenario() -> tuple[bool, bool, str, int, str, bool]:
        db = Database(core_seed.url, app_role=APP_ROLE, pool_size=1)
        try:
            async with db.autocommit_connection() as conn:
                autocommit = conn.autocommit
                idle = conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE
                cur = await conn.execute("SELECT current_user")
                row = await cur.fetchone()
                assert row is not None
                role = str(row[0])
                # Sans organisation positionnée, la RLS ne montre rien (échec fermé).
                cur = await conn.execute("SELECT count(*) FROM users")
                count_row = await cur.fetchone()
                assert count_row is not None
                visible = int(count_row[0])
            # pool_size=1 : la connexion suivante est la même ; le rôle de session est retiré.
            async with db._engine.connect() as raw:
                after_role = str((await raw.execute(text("SELECT current_user"))).scalar_one())
                driver = (await raw.get_raw_connection()).driver_connection
                assert isinstance(driver, psycopg.AsyncConnection)
                after_autocommit = bool(driver.autocommit)
            return autocommit, idle, role, visible, after_role, after_autocommit
        finally:
            await db.dispose()

    autocommit, idle, role, visible, after_role, after_autocommit = asyncio.run(scenario())
    assert autocommit
    assert idle
    assert role == APP_ROLE
    assert visible == 0
    assert after_role != APP_ROLE
    assert not after_autocommit
