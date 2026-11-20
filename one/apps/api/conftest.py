"""Fixtures partagées : une instance PostgreSQL 16 jetable pour les tests.

Ordre de résolution du serveur :
1. ``MULEMA_TEST_DATABASE_URL`` (DSN d'un rôle capable de ``CREATE DATABASE``), pour la CI ;
2. sinon ``pgserver`` (binaires PostgreSQL 16 embarqués), démarré dans un dossier temporaire.

Chaque test reçoit une base vide fraîchement créée, détruite à la fin du test.

Garde d'egress (R9) : TOUTE la suite tourne sous ``egress_guard``, quel que soit le module. Une
requête sortante hors liste blanche échoue (``EgressDeniedError``), y compris depuis un module qui
n'a rien demandé. Exceptions documentées, et seulement elles :
- le serveur PostgreSQL de test : socket Unix de ``pgserver`` (non contrôlée, ne quitte pas la
  machine), ou l'hôte:port de ``MULEMA_TEST_DATABASE_URL`` en CI ;
- la boucle locale (127.0.0.0/8, ::1, localhost), pour le serveur HealthOS simulé
  (``api.integrations.healthos_sim``), qui écoute sur un port éphémère.
Les tests qui veulent une liste plus étroite empilent leur propre garde (elle ne peut que
restreindre celle-ci).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from pgserver.postgres_server import get_server  # dépendance de test uniquement
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from api.integrations.egress import EgressAllowlist, Endpoint, egress_guard
from api.tests.contracts.helpers import apply_sql_file
from api.tests.paths import DEMO_SEED_SQL, SCHEMA_SQL

DEFAULT_PG_PORT = 5432


def _database_endpoints(dsn: str | None) -> frozenset[Endpoint]:
    """Hôte(s):port du serveur PostgreSQL de CI ; rien pour une socket Unix."""
    if not dsn:
        return frozenset()
    params = conninfo_to_dict(dsn)
    hosts = [h for h in str(params.get("host") or "").split(",") if h and not h.startswith("/")]
    ports = str(params.get("port") or DEFAULT_PG_PORT).split(",")
    return frozenset(
        Endpoint(host.lower(), int(ports[i] if i < len(ports) else ports[0]))
        for i, host in enumerate(hosts)
    )


def suite_egress_allowlist() -> EgressAllowlist:
    """Liste blanche de la suite : base de test et boucle locale (voir le docstring du module)."""
    external = _database_endpoints(os.environ.get("MULEMA_TEST_DATABASE_URL"))
    return EgressAllowlist(external, loopback=True)


@pytest.fixture(scope="session", autouse=True)
def egress_guard_for_the_suite() -> Iterator[None]:
    """R9 : aucune requête hors liste blanche, dans aucun test (``make egress``)."""
    with egress_guard(suite_egress_allowlist()):
        yield


@pytest.fixture(scope="session")
def pg_server_dsn(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """DSN administrateur d'un serveur PostgreSQL 16."""
    external = os.environ.get("MULEMA_TEST_DATABASE_URL")
    if external:
        yield external
        return

    server = get_server(tmp_path_factory.mktemp("pgdata"), cleanup_mode="stop")
    try:
        yield str(server.get_uri())
    finally:
        server.cleanup()


@pytest.fixture
def empty_db_dsn(pg_server_dsn: str) -> Iterator[str]:
    """Crée une base vide dédiée au test et renvoie son DSN."""
    name = f"insurance_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield make_conninfo(pg_server_dsn, dbname=name)
    finally:
        with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture
def insurance_dsn(empty_db_dsn: str) -> str:
    """Base vide sur laquelle ``specs/schema.sql`` a été appliqué."""
    apply_sql_file(empty_db_dsn, SCHEMA_SQL)
    return empty_db_dsn


@pytest.fixture
def seeded_dsn(insurance_dsn: str) -> str:
    """Base avec schéma + jeu de démonstration fictif (règles et seuils du PRD §5)."""
    apply_sql_file(insurance_dsn, DEMO_SEED_SQL)
    return insurance_dsn
