"""Sondes d'exploitation : ``/healthz`` (vivacité) et ``/readyz`` (base joignable, migrations à
jour). Routes d'exploitation HORS contrat d'API (CR-L10-01) : sans jeton, sans donnée
sensible (ni version, ni nom d'hôte, ni révision), absentes du schéma OpenAPI généré.

- ``/healthz`` répond 200 tant que le processus sert des requêtes ; il ne touche pas la base
  (un orchestrateur ne doit pas redémarrer l'API parce que la base est lente).
- ``/readyz`` répond 200 si la base répond sous le rôle applicatif ET si les révisions Alembic
  appliquées sont exactement les têtes du dépôt ; sinon 503 avec l'état de chaque vérification.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Final

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from api.core.database import Database
from api.core.jsonlog import LOGGER_NAME, log_event, log_exception
from api.integrations.egress import ONE_ROOT

logger = logging.getLogger(f"{LOGGER_NAME}.health")

LIVENESS_PATH: Final = "/healthz"
READINESS_PATH: Final = "/readyz"
PROBE_PATHS: Final = frozenset({LIVENESS_PATH, READINESS_PATH})
ALEMBIC_INI: Final = ONE_ROOT / "alembic.ini"
CHECK_TIMEOUT_SECONDS: Final = 3.0
_NO_STORE: Final = {"Cache-Control": "no-store"}

type HeadsLoader = Callable[[], frozenset[str]]


def repository_heads() -> frozenset[str]:
    """Têtes Alembic du dépôt (``apps/api/migrations``), sans base."""
    return frozenset(ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_heads())


class Readiness:
    """État de préparation ; les têtes du dépôt sont lues une fois, au premier appel."""

    def __init__(self, heads: HeadsLoader = repository_heads) -> None:
        self._load_heads = heads
        self._heads: frozenset[str] | None = None

    def heads(self) -> frozenset[str]:
        if self._heads is None:
            self._heads = self._load_heads()
        return self._heads

    async def check(self, database: Database | None) -> dict[str, str]:
        if database is None:
            return {"base": "injoignable", "migrations": "non_verifiee"}
        try:
            await asyncio.wait_for(database.ping(), CHECK_TIMEOUT_SECONDS)
        except Exception:  # toute panne de base = « non prête », jamais un 500
            log_exception(logger, "readiness.database_unreachable")
            return {"base": "injoignable", "migrations": "non_verifiee"}
        try:
            applied = await asyncio.wait_for(database.schema_revisions(), CHECK_TIMEOUT_SECONDS)
        except Exception:  # droit absent (CR-L10-02) ou table absente
            log_exception(logger, "readiness.revisions_unreadable")
            return {"base": "ok", "migrations": "illisible"}
        if applied != self.heads():
            log_event(logger, logging.WARNING, "readiness.migrations_behind")
            return {"base": "ok", "migrations": "en_retard"}
        return {"base": "ok", "migrations": "a_jour"}


async def _liveness(request: Request) -> Response:
    del request
    return JSONResponse({"status": "ok"}, headers=_NO_STORE)


def install_probes(app: FastAPI, readiness: Readiness | None = None) -> None:
    """Monte les deux sondes (routes Starlette, hors schéma OpenAPI)."""
    probe = readiness or Readiness()

    async def _readiness(request: Request) -> Response:
        checks = await probe.check(getattr(request.app.state, "database", None))
        ready = checks == {"base": "ok", "migrations": "a_jour"}
        return JSONResponse(
            {"status": "pret" if ready else "indisponible", "checks": checks},
            status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
            headers=_NO_STORE,
        )

    app.add_route(LIVENESS_PATH, _liveness, methods=["GET"], include_in_schema=False)
    app.add_route(READINESS_PATH, _readiness, methods=["GET"], include_in_schema=False)
