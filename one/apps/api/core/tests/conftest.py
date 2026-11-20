"""Fixtures du lot L1 : une base `insurance` par module, deux organisations fictives A et B.

Chaque organisation reçoit une ligne dans chaque table (jeu d'isolation du lot L0) et un
utilisateur par rôle. L'API tourne sous le rôle applicatif ``mulema_app`` (non propriétaire,
RLS forcée) : la connexion de test est superutilisateur, l'API fait ``SET LOCAL ROLE``.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL

from api.core.app import create_app
from api.core.identity import Identity, InMemoryIdentityProvider
from api.core.settings import Settings
from api.core.tests.probe import probe_router
from api.tests.contracts.helpers import apply_sql_file
from api.tests.paths import SCHEMA_SQL

ISOLATION_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "contracts"
    / "fixtures"
    / "one_row_per_table.sql"
)
ORG_KEYS = ("a", "b")
SEEDED_ROLES = ("admin", "gestionnaire", "medecin_conseil", "clinique", "employeur")
APP_ROLE = "mulema_app"


def sqlalchemy_url(conninfo: str) -> str:
    """Convertit un DSN libpq (clé=valeur ou URI) en URL SQLAlchemy pour psycopg async."""
    params = {k: str(v) for k, v in conninfo_to_dict(conninfo).items() if v is not None}
    database = params.pop("dbname")
    user = params.pop("user", None)
    password = params.pop("password", None)
    url = URL.create(
        "postgresql+psycopg", username=user, password=password, database=database, query=params
    )
    return url.render_as_string(hide_password=False)


@dataclass
class CoreSeed:
    """Base de test peuplée et jetons d'accès, par organisation et par rôle."""

    dsn: str
    url: str
    orgs: dict[str, UUID]
    users: dict[tuple[str, str], UUID]
    providers: dict[str, UUID]
    employers: dict[str, UUID]
    claims: dict[str, UUID]
    idp: InMemoryIdentityProvider
    tokens: dict[tuple[str, str], str] = field(default_factory=dict)

    def auth(self, org: str, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[(org, role)]}"}

    def add_user(
        self,
        org: str,
        label: str,
        roles: list[tuple[str, UUID | None, UUID | None]],
        *,
        status: str = "active",
    ) -> UUID:
        """Insère un utilisateur (en propriétaire) et lui émet un jeton."""
        org_id = self.orgs[org]
        subject = f"sub-{org}-{label}-{uuid.uuid4().hex[:8]}"
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "INSERT INTO users (organization_id, idp_subject, display_name, status) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (org_id, subject, f"Agent fictif {label}", status),
            ).fetchone()
            assert row is not None
            user_id: UUID = row[0]
            for role, provider_id, employer_id in roles:
                conn.execute(
                    "INSERT INTO user_roles (organization_id, user_id, role, provider_id, "
                    "employer_id) VALUES (%s, %s, %s, %s, %s)",
                    (org_id, user_id, role, provider_id, employer_id),
                )
        self.users[(org, label)] = user_id
        self.tokens[(org, label)] = self.idp.issue(
            Identity(subject=subject, organization_id=org_id)
        )
        return user_id


def _load_isolation_fixture(dsn: str, org: UUID, slug: str) -> None:
    script = ISOLATION_FIXTURE.read_text(encoding="utf-8")
    script = script.replace("__ORG__", str(org)).replace("__SLUG__", slug)
    with psycopg.connect(dsn) as conn:
        conn.execute(script.encode())


def _first_id(conn: psycopg.Connection, table: str, org: UUID) -> UUID:
    row = conn.execute(
        sql.SQL("SELECT id FROM {} WHERE organization_id = %s LIMIT 1").format(
            sql.Identifier(table)
        ),
        (org,),
    ).fetchone()
    assert row is not None
    value = row[0]
    assert isinstance(value, UUID)
    return value


@pytest.fixture(scope="module")
def core_seed(pg_server_dsn: str) -> Iterator[CoreSeed]:
    name = f"core_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(pg_server_dsn, dbname=name)
    try:
        apply_sql_file(dsn, SCHEMA_SQL)
        orgs = {key: uuid.uuid4() for key in ORG_KEYS}
        for key, org in orgs.items():
            _load_isolation_fixture(dsn, org, f"org-{key}")
        with psycopg.connect(dsn) as conn:
            providers = {k: _first_id(conn, "providers", o) for k, o in orgs.items()}
            employers = {k: _first_id(conn, "employers", o) for k, o in orgs.items()}
            claims = {k: _first_id(conn, "claims", o) for k, o in orgs.items()}
        seed = CoreSeed(
            dsn=dsn,
            url=sqlalchemy_url(dsn),
            orgs=orgs,
            users={},
            providers=providers,
            employers=employers,
            claims=claims,
            idp=InMemoryIdentityProvider(),
        )
        for key in ORG_KEYS:
            for role in SEEDED_ROLES:
                provider = providers[key] if role == "clinique" else None
                employer = employers[key] if role == "employeur" else None
                seed.add_user(key, role, [(role, provider, employer)])
            seed.add_user(key, "sans_role", [])
            seed.add_user(key, "desactive", [("admin", None, None)], status="disabled")
        yield seed
    finally:
        with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture(scope="module")
def client(core_seed: CoreSeed) -> Iterator[TestClient]:
    app = create_app(
        Settings(database_url=core_seed.url, app_role=APP_ROLE),
        identity_provider=core_seed.idp,
        routers=[probe_router],
    )
    with TestClient(app) as test_client:
        yield test_client


def owner_count(seed: CoreSeed, query: str, params: tuple[object, ...]) -> int:
    """Compte en propriétaire (superutilisateur : hors RLS)."""
    with psycopg.connect(seed.dsn) as conn:
        row = conn.execute(query.encode(), params).fetchone()
    assert row is not None
    return int(row[0])
