"""Q-L0-14 (c) — fonctions SECURITY DEFINER prouvées sous un propriétaire BYPASSRLS.

Point laissé ouvert par L0 : avec la RLS FORCÉE, ``resolve_organization_by_slug`` et
``resolve_payment_link`` ne voient rien si leur propriétaire n'a pas BYPASSRLS. Ici, le schéma
du contrat est appliqué PAR le propriétaire dédié ``mulema_owner`` (NOSUPERUSER, BYPASSRLS,
CREATEROLE : défaut de Q-L0-14), puis :

1. appel direct sous ``mulema_app`` : les deux fonctions résolvent ;
2. parcours complet par l'API (lien public, checkout, webhook) : les droits s'ouvrent ;
3. contrôle négatif : le même schéma avec un propriétaire SANS BYPASSRLS ne résout plus rien
   (le test 1 échouerait donc si BYPASSRLS manquait).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import psycopg
import pytest
from psycopg import sql

from api.core.identity import InMemoryIdentityProvider
from api.integrations.egress import ALLOWLIST_PATH, egress_guard, load_allowlist
from api.members.tests.support import (
    L4Env,
    OrgFixture,
    checkout,
    create_database,
    drop_database,
    hook,
    payment_link_token,
    post_webhook,
    seed_organization,
    start_client,
    suspended_member,
)
from api.tests.contracts.helpers import APP_ROLE
from api.tests.paths import SCHEMA_SQL

OWNER = "mulema_owner"


@dataclass
class OwnedDatabase:
    admin_dsn: str
    dsn: str
    orgs: dict[str, OrgFixture]
    idp: InMemoryIdentityProvider


@pytest.fixture(scope="module")
def owned_db(pg_server_dsn: str) -> Iterator[OwnedDatabase]:
    with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
        exists = admin.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (OWNER,)).fetchone()
        if exists is None:
            admin.execute(
                sql.SQL(
                    "CREATE ROLE {} NOLOGIN NOSUPERUSER BYPASSRLS CREATEROLE NOCREATEDB"
                ).format(sql.Identifier(OWNER))
            )
    dsn = create_database(pg_server_dsn, "l4_owner")
    try:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                    sql.Identifier(str(psycopg.conninfo.conninfo_to_dict(dsn)["dbname"])),
                    sql.Identifier(OWNER),
                )
            )
        with psycopg.connect(dsn) as conn:
            # Le contrat est joué PAR le propriétaire : il possède tables et fonctions.
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(OWNER)))
            conn.execute(SCHEMA_SQL.read_text(encoding="utf-8").encode())
        idp = InMemoryIdentityProvider()
        orgs = {key: seed_organization(dsn, key, idp) for key in ("a", "b")}
        yield OwnedDatabase(pg_server_dsn, dsn, orgs, idp)
    finally:
        drop_database(pg_server_dsn, dsn)


def _as_app(dsn: str, query: str, params: tuple[object, ...]) -> list[tuple[object, ...]]:
    """Exécute sous ``mulema_app`` SANS organisation positionnée (cas webhook / lien public)."""
    with psycopg.connect(dsn) as conn:
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(APP_ROLE)))
        return list(conn.execute(query.encode(), params).fetchall())


def test_le_proprietaire_est_dedie_bypassrls_et_non_superutilisateur(
    owned_db: OwnedDatabase,
) -> None:
    with psycopg.connect(owned_db.dsn) as conn:
        owners = conn.execute(
            "SELECT p.proname, r.rolname, r.rolsuper, r.rolbypassrls, p.prosecdef "
            "FROM pg_proc p JOIN pg_roles r ON r.oid = p.proowner "
            "WHERE p.proname IN ('resolve_organization_by_slug', 'resolve_payment_link') "
            "ORDER BY p.proname"
        ).fetchall()
        table_owner = conn.execute(
            "SELECT tableowner FROM pg_tables WHERE tablename = 'organizations'"
        ).fetchone()
    assert owners == [
        ("resolve_organization_by_slug", OWNER, False, True, True),
        ("resolve_payment_link", OWNER, False, True, True),
    ]
    assert table_owner == (OWNER,)


def test_resolution_directe_sous_le_role_applicatif(owned_db: OwnedDatabase) -> None:
    org = owned_db.orgs["a"]
    # Sans organisation positionnée, mulema_app ne voit aucune organisation (RLS forcée)…
    assert _as_app(owned_db.dsn, "SELECT count(*) FROM organizations", ()) == [(0,)]
    # … mais la fonction du contrat résout le slug.
    assert _as_app(owned_db.dsn, "SELECT resolve_organization_by_slug(%s)", (org.slug,)) == [
        (org.id,)
    ]
    assert _as_app(owned_db.dsn, "SELECT resolve_organization_by_slug(%s)", ("slug-inconnu",)) == [
        (None,)
    ]


def test_parcours_complet_par_l_api(owned_db: OwnedDatabase) -> None:
    with (
        start_client(owned_db.dsn, owned_db.idp, owned_db.orgs) as env,
        egress_guard(load_allowlist(ALLOWLIST_PATH, country="CI")),
    ):
        member, contribution = suspended_member(env, "a")
        token = payment_link_token(env, "a", contribution)

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        resolved = _as_app(owned_db.dsn, "SELECT * FROM resolve_payment_link(%s)", (token_hash,))
        assert resolved == [(owned_db.orgs["a"].id, contribution)]

        page = env.client.get(f"/v1/public/payment-links/{token}")
        assert page.status_code == 200, page.text
        payment = checkout(env, token)
        note = env.simulated("wave").notification(payment, occurred_at=env.clock.now())
        ack = post_webhook(env, hook(owned_db.orgs["a"].slug, "wave"), note.body, note.signature)
        assert ack.json() == {"received": True, "duplicate": False}
        rights = env.client.get(
            f"/v1/members/{member['id']}/entitlements", headers=env.auth("a", "gestionnaire")
        ).json()
        assert rights["rights_open"] is True
        _check_owner_cannot_be_api(env)


def _check_owner_cannot_be_api(env: L4Env) -> None:
    """L'API tourne sous mulema_app, jamais sous le propriétaire BYPASSRLS."""

    async def current_user() -> str:
        from sqlalchemy import text  # noqa: PLC0415

        async with env.database.transaction(None) as session:
            return str((await session.execute(text("SELECT current_user"))).scalar_one())

    assert env.run(current_user) == APP_ROLE


def test_controle_negatif_proprietaire_sans_bypassrls(owned_db: OwnedDatabase) -> None:
    org = owned_db.orgs["b"]
    weak = f"mulema_owner_sans_bypass_{uuid.uuid4().hex[:8]}"
    functions = ("resolve_organization_by_slug(text)", "resolve_payment_link(text)")
    with psycopg.connect(owned_db.dsn, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(weak))
        )
        admin.execute(
            sql.SQL("GRANT SELECT ON organizations, payment_links TO {}").format(
                sql.Identifier(weak)
            )
        )
        for function in functions:
            admin.execute(
                sql.SQL("ALTER FUNCTION {} OWNER TO {}").format(
                    sql.SQL(function), sql.Identifier(weak)
                )
            )
    try:
        assert _as_app(owned_db.dsn, "SELECT resolve_organization_by_slug(%s)", (org.slug,)) == [
            (None,)
        ]
    finally:
        with psycopg.connect(owned_db.dsn, autocommit=True) as admin:
            for function in functions:
                admin.execute(
                    sql.SQL("ALTER FUNCTION {} OWNER TO {}").format(
                        sql.SQL(function), sql.Identifier(OWNER)
                    )
                )
            admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(weak)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(weak)))
    # Propriétaire rétabli : la résolution refonctionne.
    assert _as_app(owned_db.dsn, "SELECT resolve_organization_by_slug(%s)", (org.slug,)) == [
        (org.id,)
    ]
