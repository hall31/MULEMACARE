"""Contrat L0 : la chaîne Alembic (0001, 0002…) produit exactement ``specs/schema.sql``.

Les contraintes de 0002 sont éprouvées sur la base MIGRÉE par Alembic (et pas seulement sur
``specs/schema.sql``) : une migration qui oublie ou affaiblit une contrainte fait échouer
``test_0002_refuse_sur_la_base_migree`` et ``test_head_alembic_egale_le_contrat``.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from typing import Literal

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from api.tests.contracts.helpers import apply_sql_file
from api.tests.paths import ALEMBIC_INI, ONE_ROOT, SCHEMA_SQL


def _sqlalchemy_url(dsn: str) -> str:
    params = conninfo_to_dict(dsn)
    host = params.get("host", "")
    user = params.get("user", "postgres")
    port = params.get("port", "5432")
    dbname = params["dbname"]
    if str(host).startswith("/"):
        return f"postgresql+psycopg://{user}@/{dbname}?host={host}&port={port}"
    password = params.get("password")
    auth = f"{user}:{password}" if password else str(user)
    return f"postgresql+psycopg://{auth}@{host}:{port}/{dbname}"


def _config(dsn: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", _sqlalchemy_url(dsn).replace("%", "%%"))
    return cfg


def test_upgrade_head_sur_base_vide(empty_db_dsn: str) -> None:
    command.upgrade(_config(empty_db_dsn), "head")
    with psycopg.connect(empty_db_dsn) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' "
            "AND table_name IN ('claims', 'ledger_entries', 'ledger_lines', 'audit_events')"
        ).fetchone()
    assert version == (HEAD,)
    assert tables == (4,)


def test_downgrade_de_0001_refuse(empty_db_dsn: str) -> None:
    """Revenir avant 0001 détruirait des données : interdit sans validation humaine."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "0001")
    with pytest.raises(RuntimeError, match="validation humaine"):
        command.downgrade(cfg, "base")


def test_downgrade_de_0002_refuse(empty_db_dsn: str) -> None:
    """Retirer member_id effacerait les comptes adhérents : interdit sans validation humaine."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "0002")
    with pytest.raises(RuntimeError, match="validation humaine"):
        command.downgrade(cfg, "0001")


HEAD = "0006"
VERSIONS = ONE_ROOT / "apps" / "api" / "migrations" / "versions"
SQL_0002 = VERSIONS / "0002_espace_adherent.sql"
SQL_0003 = VERSIONS / "0003_mesure_produit.sql"
SQL_0004 = VERSIONS / "0004_marque_blanche_partenaires.sql"
SQL_0005 = VERSIONS / "0005_preuve_de_domaine.sql"
SQL_0006 = VERSIONS / "0006_import_existant.sql"
FROZEN_0001 = ONE_ROOT / "apps" / "api" / "migrations" / "versions" / "0001_schema_initial.sql"
# Empreinte figée de la migration 0001 : elle ne change plus après sa relecture humaine.
# Toute évolution du schéma passe par une migration 0002+ et met à jour specs/schema.sql.
FROZEN_0001_SHA256 = "6ccc4fa748a635b5d99d19949dc1b306531ef7a0c9e703f6fca63d627c127e05"


def test_migration_0001_figee() -> None:
    digest = hashlib.sha256(FROZEN_0001.read_bytes()).hexdigest()
    assert digest == FROZEN_0001_SHA256


def _catalog(dsn: str) -> set[tuple[str, str, str, str]]:
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM information_schema.columns WHERE table_schema = 'public' "
            "AND table_name <> 'alembic_version'"
        ).fetchall()
    return {(r[0], r[1], r[2], r[3]) for r in rows}


# Catalogue complet comparé entre la base migrée par Alembic et specs/schema.sql : colonnes, mais
# aussi contraintes AVEC leur définition (CHECK, FK, UNIQUE, PK), index, RLS, politiques,
# déclencheurs, fonctions et droits. Une contrainte retirée ou affaiblie dans une migration
# (mutation M13) rend la base migrée différente du contrat, même si les colonnes sont identiques.
_SCHEMA_CATALOG: dict[str, str] = {
    "colonnes": (
        "SELECT table_name, column_name, data_type, is_nullable, "
        "coalesce(column_default, '') FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
    ),
    "contraintes": (
        "SELECT conrelid::regclass::text, conname, contype::text, pg_get_constraintdef(oid) "
        "FROM pg_constraint WHERE connamespace = 'public'::regnamespace "
        "AND conrelid::regclass::text <> 'alembic_version'"
    ),
    "index": (
        "SELECT tablename, indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
    ),
    "rls": (
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
        "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' "
        "AND relname <> 'alembic_version'"
    ),
    "politiques": (
        "SELECT tablename, policyname, cmd, roles::text, coalesce(qual, ''), "
        "coalesce(with_check, '') FROM pg_policies WHERE schemaname = 'public'"
    ),
    "declencheurs": (
        "SELECT tgrelid::regclass::text, tgname, pg_get_triggerdef(oid) FROM pg_trigger "
        "WHERE NOT tgisinternal"
    ),
    "fonctions": (
        "SELECT proname, pg_get_functiondef(oid) FROM pg_proc "
        "WHERE pronamespace = 'public'::regnamespace"
    ),
    "droits": (
        "SELECT table_name, grantee, privilege_type FROM information_schema.role_table_grants "
        "WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
    ),
}


def _schema_catalog(dsn: str) -> dict[str, set[tuple[object, ...]]]:
    with psycopg.connect(dsn) as conn:
        return {
            kind: {tuple(row) for row in conn.execute(query.encode()).fetchall()}
            for kind, query in _SCHEMA_CATALOG.items()
        }


def test_head_alembic_egale_le_contrat(empty_db_dsn: str, pg_server_dsn: str) -> None:
    """specs/schema.sql décrit exactement l'état obtenu par toutes les migrations."""
    command.upgrade(_config(empty_db_dsn), "head")
    migrated = _schema_catalog(empty_db_dsn)
    with psycopg.connect(empty_db_dsn, autocommit=True) as conn:
        conn.execute("CREATE DATABASE contrat_reference")
    reference_dsn = make_conninfo(empty_db_dsn, dbname="contrat_reference")
    try:
        apply_sql_file(reference_dsn, SCHEMA_SQL)
        reference = _schema_catalog(reference_dsn)
    finally:
        with psycopg.connect(pg_server_dsn, autocommit=True) as conn:
            conn.execute("DROP DATABASE IF EXISTS contrat_reference WITH (FORCE)")
    for kind in _SCHEMA_CATALOG:
        assert migrated[kind], f"{kind} : catalogue vide (requête fausse ?)"
        only_migrated = sorted(map(str, migrated[kind] - reference[kind]))
        only_contract = sorted(map(str, reference[kind] - migrated[kind]))
        assert (only_migrated, only_contract) == ([], []), (
            f"{kind} : seulement dans la base migrée {only_migrated}, "
            f"seulement dans specs/schema.sql {only_contract}"
        )


# --- 0002 : espace adhérent (CR-P1-01), additive et rejouable -----------------------------------


def _constraints(dsn: str) -> set[tuple[str, str]]:
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT conrelid::regclass::text, conname FROM pg_constraint "
            "WHERE connamespace = 'public'::regnamespace"
        ).fetchall()
    return {(r[0], r[1]) for r in rows}


def test_0002_est_additive(empty_db_dsn: str) -> None:
    """0001 → 0002 n'enlève ni colonne ni contrainte, et garde les lignes existantes."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "0001")
    before_columns, before_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    with psycopg.connect(empty_db_dsn) as conn:
        conn.execute(
            "INSERT INTO organizations (id, slug, name, country_code, timezone, capabilities) "
            "VALUES ('00000000-0000-4000-8000-0000000000aa', 'org-migr', 'Org fictive', 'CI', "
            "'Africa/Abidjan', ARRAY['gestionnaire'])"
        )
        conn.execute(
            "INSERT INTO users (organization_id, idp_subject, display_name) VALUES "
            "('00000000-0000-4000-8000-0000000000aa', 'sub-migr', 'Agent fictif')"
        )
        conn.execute(
            "INSERT INTO user_roles (organization_id, user_id, role) SELECT organization_id, "
            "id, 'gestionnaire' FROM users WHERE idp_subject = 'sub-migr'"
        )
    command.upgrade(cfg, "0002")
    after_columns, after_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    assert before_columns < after_columns
    assert after_columns - before_columns == {("user_roles", "member_id", "uuid", "YES")}
    assert before_constraints <= after_constraints
    with psycopg.connect(empty_db_dsn) as conn:
        kept = conn.execute("SELECT role, member_id FROM user_roles").fetchall()
    assert kept == [("gestionnaire", None)]


def test_0002_rejouable(empty_db_dsn: str) -> None:
    """Le SQL de 0002 rejoué sur une base déjà migrée ne change rien et n'échoue pas."""
    command.upgrade(_config(empty_db_dsn), "head")
    columns, constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    apply_sql_file(empty_db_dsn, SQL_0002)
    apply_sql_file(empty_db_dsn, SQL_0002)
    assert _catalog(empty_db_dsn) == columns
    assert _constraints(empty_db_dsn) == constraints


@pytest.mark.parametrize(
    ("role", "with_member", "accepted"),
    [
        ("adherent", True, True),
        ("adherent", False, False),
        ("gestionnaire", True, False),
    ],
)
def test_0002_member_id_reserve_a_l_adherent(
    insurance_dsn: str, role: str, with_member: bool, accepted: bool
) -> None:
    """Contrainte du contrat : member_id présent si et seulement si le rôle est adherent."""
    script = (ONE_ROOT / "apps" / "api" / "tests" / "contracts" / "fixtures").joinpath(
        "one_row_per_table.sql"
    )
    org = "00000000-0000-4000-8000-0000000000bb"
    with psycopg.connect(insurance_dsn) as conn:
        text = script.read_text(encoding="utf-8")
        conn.execute(text.replace("__ORG__", org).replace("__SLUG__", "org-p1").encode())
        member = conn.execute("SELECT id FROM members WHERE organization_id = %s", (org,))
        member_id = member.fetchone()
        user = conn.execute("SELECT id FROM users WHERE organization_id = %s LIMIT 1", (org,))
        user_id = user.fetchone()
        assert member_id is not None
        assert user_id is not None
        statement = (
            "INSERT INTO user_roles (organization_id, user_id, role, member_id) "
            "VALUES (%s, %s, %s, %s)"
        )
        params = (org, user_id[0], role, member_id[0] if with_member else None)
        if accepted:
            conn.execute(statement, params)
        else:
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(statement, params)


# --- 0002 éprouvée sur la base MIGRÉE par Alembic (mutation M13) --------------------------------

ISOLATION_FIXTURE = ONE_ROOT / "apps" / "api" / "tests" / "contracts" / "fixtures"
MemberRef = Literal["own", "other_org", "unknown", "none", "not_uuid"]


@pytest.fixture(scope="module")
def migrated_dsn(pg_server_dsn: str) -> Iterator[str]:
    """Base migrée par la chaîne Alembic jusqu'à head, avec deux organisations fictives."""
    name = f"migrated_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(pg_server_dsn, dbname=name)
    try:
        command.upgrade(_config(dsn), "head")
        script = (ISOLATION_FIXTURE / "one_row_per_table.sql").read_text(encoding="utf-8")
        with psycopg.connect(dsn) as conn:
            version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            assert version == (HEAD,), "la base doit venir d'Alembic, pas de specs/schema.sql"
            for org, slug in ((ORG_P1, "org-p1"), (ORG_OTHER, "org-autre")):
                conn.execute(script.replace("__ORG__", org).replace("__SLUG__", slug).encode())
        yield dsn
    finally:
        with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


ORG_P1 = "00000000-0000-4000-8000-0000000000c1"
ORG_OTHER = "00000000-0000-4000-8000-0000000000c2"


def _member_value(conn: psycopg.Connection, ref: MemberRef) -> str | None:
    if ref == "none":
        return None
    if ref == "unknown":
        return str(uuid.uuid4())
    if ref == "not_uuid":
        return "pas-un-uuid"
    org = ORG_P1 if ref == "own" else ORG_OTHER
    row = conn.execute("SELECT id FROM members WHERE organization_id = %s", (org,)).fetchone()
    assert row is not None
    return str(row[0])


def _insert_role(conn: psycopg.Connection, role: str, member: MemberRef) -> None:
    user = conn.execute("SELECT id FROM users WHERE organization_id = %s", (ORG_P1,)).fetchone()
    assert user is not None
    conn.execute(
        "INSERT INTO user_roles (organization_id, user_id, role, member_id) "
        "VALUES (%s, %s, %s, %s)",
        (ORG_P1, user[0], role, _member_value(conn, member)),
    )


# (rôle, contrat visé, erreur attendue, contrainte de 0002 en cause) ; None = accepté.
_REFUSALS: list[tuple[str, MemberRef, type[psycopg.Error] | None, str | None]] = [
    ("adherent", "own", None, None),
    ("adherent", "none", psycopg.errors.CheckViolation, "user_roles_adherent_scope_check"),
    ("gestionnaire", "own", psycopg.errors.CheckViolation, "user_roles_adherent_scope_check"),
    ("admin", "own", psycopg.errors.CheckViolation, "user_roles_adherent_scope_check"),
    ("role_inconnu", "none", psycopg.errors.CheckViolation, "user_roles_role_check"),
    ("adherent", "other_org", psycopg.errors.ForeignKeyViolation, "user_roles_member_fk"),
    ("adherent", "unknown", psycopg.errors.ForeignKeyViolation, "user_roles_member_fk"),
    ("adherent", "not_uuid", psycopg.errors.InvalidTextRepresentation, None),
]


@pytest.mark.parametrize(
    ("role", "member", "error", "constraint"),
    _REFUSALS,
    ids=[f"{r}-{m}" for r, m, _, _ in _REFUSALS],
)
def test_0002_refuse_sur_la_base_migree(
    migrated_dsn: str,
    role: str,
    member: MemberRef,
    error: type[psycopg.Error] | None,
    constraint: str | None,
) -> None:
    """Rôle adherent accepté ; member_id réservé à adherent, du même organisme, de type uuid."""
    with psycopg.connect(migrated_dsn) as conn:
        try:
            if error is None:
                _insert_role(conn, role, member)
                return
            with pytest.raises(error) as caught:
                _insert_role(conn, role, member)
            assert caught.value.diag.constraint_name == constraint
        finally:
            conn.rollback()


def test_0002_refuse_un_contrat_sur_un_role_existant(migrated_dsn: str) -> None:
    """Une ligne existante (rôle clinique de 0001) ne peut pas recevoir de member_id."""
    with psycopg.connect(migrated_dsn) as conn:
        member = _member_value(conn, "own")
        with pytest.raises(psycopg.errors.CheckViolation) as caught:
            conn.execute(
                "UPDATE user_roles SET member_id = %s WHERE organization_id = %s "
                "AND role = 'clinique'",
                (member, ORG_P1),
            )
        assert caught.value.diag.constraint_name == "user_roles_adherent_scope_check"
        conn.rollback()


def test_0002_objets_presents_sur_la_base_migree(migrated_dsn: str) -> None:
    """Colonne, contraintes et index de 0002, avec leur définition, sur la base Alembic."""
    with psycopg.connect(migrated_dsn) as conn:
        column = conn.execute(
            "SELECT data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'user_roles' AND column_name = 'member_id'"
        ).fetchone()
        constraints: dict[str, str] = dict(
            conn.execute(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'user_roles'::regclass AND conname IN "
                "('user_roles_role_check', 'user_roles_adherent_scope_check', "
                "'user_roles_member_fk')"
            ).fetchall()
        )
        index = conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'user_roles_member_idx'"
        ).fetchone()
    assert column == ("uuid", "YES")
    assert "'adherent'::text" in constraints["user_roles_role_check"]
    assert constraints["user_roles_adherent_scope_check"] == (
        "CHECK (((role = 'adherent'::text) = (member_id IS NOT NULL)))"
    )
    assert constraints["user_roles_member_fk"] == (
        "FOREIGN KEY (organization_id, member_id) REFERENCES members(organization_id, id)"
    )
    assert index is not None
    assert index[0].endswith("USING btree (organization_id, member_id)")


# --- 0003 : mesure produit (CR-P2-01), additive et rejouable -----------------------------------


def test_downgrade_de_0003_refuse(empty_db_dsn: str) -> None:
    """Retirer product_events effacerait la mesure : interdit sans validation humaine."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "0003")
    with pytest.raises(RuntimeError, match="validation humaine"):
        command.downgrade(cfg, "0002")


def test_0003_est_additive(empty_db_dsn: str) -> None:
    """0002 → 0003 n'ajoute que la table product_events, n'enlève rien, ne réécrit rien."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "0002")
    before_columns, before_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    with psycopg.connect(empty_db_dsn) as conn:
        conn.execute(
            "INSERT INTO organizations (id, slug, name, country_code, timezone, capabilities) "
            "VALUES ('00000000-0000-4000-8000-0000000000ab', 'org-p2', 'Org fictive', 'CI', "
            "'Africa/Abidjan', ARRAY['gestionnaire'])"
        )
    command.upgrade(cfg, "0003")
    after_columns, after_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    assert before_columns < after_columns
    assert {c[0] for c in after_columns - before_columns} == {"product_events"}
    assert before_constraints < after_constraints
    assert {c[0] for c in after_constraints - before_constraints} == {"product_events"}
    with psycopg.connect(empty_db_dsn) as conn:
        kept = conn.execute("SELECT slug FROM organizations").fetchall()
    assert kept == [("org-p2",)]


def test_0003_rejouable(empty_db_dsn: str) -> None:
    """Le SQL de 0003 rejoué sur une base déjà migrée ne change rien et n'échoue pas."""
    command.upgrade(_config(empty_db_dsn), "head")
    before = _schema_catalog(empty_db_dsn)
    apply_sql_file(empty_db_dsn, SQL_0003)
    apply_sql_file(empty_db_dsn, SQL_0003)
    assert _schema_catalog(empty_db_dsn) == before


def test_0003_isolation_et_droits_sur_la_base_migree(migrated_dsn: str) -> None:
    """RLS forcée, politique unique tenant_isolation, droits SELECT/INSERT/DELETE sans UPDATE."""
    with psycopg.connect(migrated_dsn) as conn:
        flags = conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = 'product_events'::regclass"
        ).fetchone()
        policies = conn.execute(
            "SELECT policyname, cmd, qual, with_check FROM pg_policies "
            "WHERE tablename = 'product_events'"
        ).fetchall()
        rights = {
            r[0]
            for r in conn.execute(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE table_name = 'product_events' AND grantee = 'mulema_app'"
            ).fetchall()
        }
    qual = "(organization_id = app_current_organization_id())"
    assert flags == (True, True)
    assert policies == [("tenant_isolation", "ALL", qual, qual)]
    assert rights == {"SELECT", "INSERT", "DELETE"}


# --- 0004 : marque blanche, assureur, employeur, accueil (CR-P3-01), additive et rejouable -----

P3_TABLES = frozenset({"organization_branding", "configuration_templates"})


def test_downgrade_de_0004_refuse(empty_db_dsn: str) -> None:
    """Retirer la marque et les gabarits effacerait des données : validation humaine exigée."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "head")
    with pytest.raises(RuntimeError, match="validation humaine"):
        command.downgrade(cfg, "0003")


def test_0004_est_additive(empty_db_dsn: str) -> None:
    """0003 → 0004 : deux tables nouvelles, trois listes élargies, rien de retiré ni réécrit."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "0003")
    before_columns, before_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    with psycopg.connect(empty_db_dsn) as conn:
        conn.execute(
            "INSERT INTO organizations (id, slug, name, country_code, timezone, capabilities) "
            "VALUES ('00000000-0000-4000-8000-0000000000ac', 'org-p3', 'Org fictive', 'CI', "
            "'Africa/Abidjan', ARRAY['porteur_de_risque', 'gestionnaire'])"
        )
        conn.execute(
            "INSERT INTO users (organization_id, idp_subject, display_name) VALUES "
            "('00000000-0000-4000-8000-0000000000ac', 'sub-p3', 'Agent fictif')"
        )
        conn.execute(
            "INSERT INTO user_roles (organization_id, user_id, role) SELECT organization_id, "
            "id, 'admin' FROM users WHERE idp_subject = 'sub-p3'"
        )
    command.upgrade(cfg, "0004")
    after_columns, after_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    assert before_columns < after_columns
    assert {c[0] for c in after_columns - before_columns} == P3_TABLES
    # Les trois listes élargies gardent leur nom : même ensemble de contraintes hors tables P3.
    assert before_constraints < after_constraints
    assert {c[0] for c in after_constraints - before_constraints} == P3_TABLES
    with psycopg.connect(empty_db_dsn) as conn:
        kept = conn.execute(
            "SELECT o.slug, o.capabilities, r.role FROM organizations o "
            "JOIN user_roles r ON r.organization_id = o.id"
        ).fetchall()
    assert kept == [("org-p3", ["porteur_de_risque", "gestionnaire"], "admin")]


def test_0004_rejouable(empty_db_dsn: str) -> None:
    """Le SQL de 0004 rejoué sur une base migrée en 0004 ne change rien et n'échoue pas.

    (Sur head, il remettrait l'ancienne ``resolve_organization_branding`` que 0005 remplace :
    on rejoue une migration sur l'état qu'elle produit.)"""
    command.upgrade(_config(empty_db_dsn), "0004")
    before = _schema_catalog(empty_db_dsn)
    apply_sql_file(empty_db_dsn, SQL_0004)
    apply_sql_file(empty_db_dsn, SQL_0004)
    assert _schema_catalog(empty_db_dsn) == before


def test_0004_isolation_et_droits_sur_la_base_migree(migrated_dsn: str) -> None:
    """RLS forcée et politique unique ; marque : SELECT/INSERT/UPDATE ; gabarits : ajout seul."""
    qual = "(organization_id = app_current_organization_id())"
    expected_rights = {
        "organization_branding": {"SELECT", "INSERT", "UPDATE"},
        "configuration_templates": {"SELECT", "INSERT"},
    }
    with psycopg.connect(migrated_dsn) as conn:
        for table, rights in expected_rights.items():
            flags = conn.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass",
                (table,),
            ).fetchone()
            policies = conn.execute(
                "SELECT policyname, cmd, qual, with_check FROM pg_policies WHERE tablename = %s",
                (table,),
            ).fetchall()
            granted = {
                r[0]
                for r in conn.execute(
                    "SELECT privilege_type FROM information_schema.role_table_grants "
                    "WHERE table_name = %s AND grantee = 'mulema_app'",
                    (table,),
                ).fetchall()
            }
            assert flags == (True, True), table
            assert policies == [("tenant_isolation", "ALL", qual, qual)], table
            assert granted == rights, table


def _app(conn: psycopg.Connection, org: str) -> None:
    conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier("mulema_app")))
    conn.execute("SELECT set_config('app.organization_id', %s, false)", (org,))


@pytest.mark.parametrize(
    ("theme", "accepted"),
    [
        pytest.param('{"light": {"accent": "#1d4ed8"}, "dark": {}}', True, id="liste-fermee"),
        pytest.param('{"light": {"bg": "#000000"}}', False, id="jeton-hors-liste"),
        pytest.param('{"sun": {"accent": "#1d4ed8"}}', False, id="plein-soleil"),
        pytest.param('{"light": {"accent": "red"}}', False, id="couleur-libre"),
        pytest.param('{"light": {"accent": "#1D4ED8"}}', False, id="majuscules"),
        pytest.param('{"light": {"accent": 1}}', False, id="nombre"),
        pytest.param('{"light": "#1d4ed8"}', False, id="theme-non-objet"),
        pytest.param('["#1d4ed8"]', False, id="tableau"),
    ],
)
def test_0004_liste_fermee_des_jetons_gardee_par_la_base(
    migrated_dsn: str, theme: str, accepted: bool
) -> None:
    """Mutation « liste fermée retirée de l'API » : la base refuse encore, sous mulema_app."""
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        statement = "UPDATE organization_branding SET theme = %s::jsonb WHERE organization_id = %s"
        try:
            if accepted:
                assert conn.execute(statement, (theme, ORG_P1)).rowcount == 1
            else:
                with pytest.raises(psycopg.errors.CheckViolation) as caught:
                    conn.execute(statement, (theme, ORG_P1))
                assert caught.value.diag.constraint_name == "organization_branding_theme_check"
        finally:
            conn.rollback()


@pytest.mark.parametrize(
    ("kind", "src"),
    [
        pytest.param("url", "javascript:alert(1)", id="javascript"),
        pytest.param("url", "//cdn.example.com/x.png", id="protocole-relatif"),
        pytest.param("data_uri", "data:text/html;base64,PHNjcmlwdD4=", id="html"),
        pytest.param("url", None, id="type-sans-source"),
    ],
)
def test_0004_logo_executable_refuse_par_la_base(
    migrated_dsn: str, kind: str, src: str | None
) -> None:
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(
                    "UPDATE organization_branding SET logo_kind = %s, logo_src = %s "
                    "WHERE organization_id = %s",
                    (kind, src, ORG_P1),
                )
        finally:
            conn.rollback()


def test_0004_gabarit_en_ajout_seul(migrated_dsn: str) -> None:
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            with pytest.raises(psycopg.Error) as caught:
                conn.execute("UPDATE configuration_templates SET label = 'modifié'")
            assert caught.value.sqlstate in {"42501", "MCL01"}
        finally:
            conn.rollback()
    with psycopg.connect(migrated_dsn) as conn, pytest.raises(psycopg.Error) as owner:
        conn.execute("DELETE FROM configuration_templates")  # même le propriétaire
    assert owner.value.sqlstate == "MCL01"


def test_0004_admin_plateforme_hors_organisation_plateforme_refuse(migrated_dsn: str) -> None:
    """Mutation « garde de rôle retirée de l'API » : la base refuse encore le rôle (MCP01)."""
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            with pytest.raises(psycopg.Error) as caught:
                _insert_role(conn, "admin_plateforme", "none")
            assert caught.value.sqlstate == "MCP01"
        finally:
            conn.rollback()


def test_0004_creation_d_organisation_refusee_hors_plateforme(migrated_dsn: str) -> None:
    """Un admin d'organisation ordinaire n'obtient rien de la fonction de création (MCP01)."""
    with psycopg.connect(migrated_dsn) as conn:
        user = conn.execute("SELECT id FROM users WHERE organization_id = %s", (ORG_P1,)).fetchone()
        assert user is not None
        _app(conn, ORG_P1)
        try:
            with pytest.raises(psycopg.Error) as caught:
                conn.execute(
                    "SELECT platform_create_organization(%s, 'intrus', 'Intrus', 'CI', "
                    "'Africa/Abidjan', ARRAY['gestionnaire'], NULL)",
                    (user[0],),
                )
            assert caught.value.sqlstate == "MCP01"
        finally:
            conn.rollback()


def test_0004_fonctions_reservees_au_role_applicatif(migrated_dsn: str) -> None:
    with psycopg.connect(migrated_dsn) as conn:
        rows = conn.execute(
            "SELECT p.proname, has_function_privilege('public', p.oid, 'EXECUTE'), "
            "has_function_privilege('mulema_app', p.oid, 'EXECUTE'), p.prosecdef "
            "FROM pg_proc p WHERE p.proname IN "
            "('resolve_organization_branding', 'platform_create_organization')"
        ).fetchall()
    assert sorted(rows) == [
        ("platform_create_organization", False, True, True),
        ("resolve_organization_branding", False, True, True),
    ]


# --- 0005 : preuve de propriété du domaine (CR-P3-02), additive et rejouable -------------------


def test_downgrade_de_0005_refuse(empty_db_dsn: str) -> None:
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "head")
    with pytest.raises(RuntimeError, match="validation humaine"):
        command.downgrade(cfg, "0004")


def test_0005_est_additive(empty_db_dsn: str) -> None:
    """0004 → 0005 : deux colonnes et deux contraintes sur organization_branding, rien de retiré ;
    un domaine déjà déclaré est gardé, en attente de preuve (aucune ligne réécrite)."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "0004")
    before_columns, before_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    org = "00000000-0000-4000-8000-0000000000ad"
    with psycopg.connect(empty_db_dsn) as conn:
        conn.execute(
            "INSERT INTO organizations (id, slug, name, country_code, timezone, capabilities) "
            "VALUES (%s, 'org-p3b', 'Org fictive', 'CI', 'Africa/Abidjan', "
            "ARRAY['gestionnaire'])",
            (org,),
        )
        conn.execute(
            "INSERT INTO organization_branding (organization_id, display_name, custom_domain) "
            "VALUES (%s, 'Marque fictive', 'sante.org-p3b.ci')",
            (org,),
        )
    command.upgrade(cfg, "0005")
    after_columns, after_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    assert before_columns < after_columns
    assert {(c[0], c[1]) for c in after_columns - before_columns} == {
        ("organization_branding", "custom_domain_token"),
        ("organization_branding", "custom_domain_verified_at"),
    }
    assert before_constraints < after_constraints
    assert after_constraints - before_constraints == {
        ("organization_branding", "organization_branding_domain_token_check"),
        ("organization_branding", "organization_branding_domain_proof_check"),
    }
    with psycopg.connect(empty_db_dsn) as conn:
        kept = conn.execute(
            "SELECT display_name, custom_domain, custom_domain_token, custom_domain_verified_at "
            "FROM organization_branding"
        ).fetchall()
    assert kept == [("Marque fictive", "sante.org-p3b.ci", None, None)]


def test_0005_rejouable(empty_db_dsn: str) -> None:
    command.upgrade(_config(empty_db_dsn), "head")
    before = _schema_catalog(empty_db_dsn)
    apply_sql_file(empty_db_dsn, SQL_0005)
    apply_sql_file(empty_db_dsn, SQL_0005)
    assert _schema_catalog(empty_db_dsn) == before


PROOF = "ab" * 16  # jeton fictif de 32 hexadécimaux


def _brand(conn: psycopg.Connection, domain: str | None, token: str | None) -> None:
    conn.execute(
        "UPDATE organization_branding SET custom_domain = %s, custom_domain_token = %s "
        "WHERE organization_id = %s",
        (domain, token, ORG_P1),
    )


def test_0005_une_preuve_ne_s_herite_pas(migrated_dsn: str) -> None:
    """Mutation « l'API garde la preuve en changeant de domaine » : la base l'efface encore."""
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            _brand(conn, "a.fictif.ci", PROOF)
            conn.execute(
                "UPDATE organization_branding SET custom_domain_verified_at = now() "
                "WHERE organization_id = %s",
                (ORG_P1,),
            )
            conn.execute(
                "UPDATE organization_branding SET custom_domain = 'autre.fictif.ci' "
                "WHERE organization_id = %s",
                (ORG_P1,),
            )
            moved = conn.execute(
                "SELECT custom_domain_verified_at FROM organization_branding "
                "WHERE organization_id = %s",
                (ORG_P1,),
            ).fetchone()
            assert moved == (None,)
        finally:
            conn.rollback()


@pytest.mark.parametrize(
    ("domain", "token", "verified"),
    [
        pytest.param(None, PROOF, False, id="jeton-sans-domaine"),
        pytest.param("a.fictif.ci", "pas-un-jeton", False, id="jeton-mal-forme"),
    ],
)
def test_0005_preuve_coherente_gardee_par_la_base(
    migrated_dsn: str, domain: str | None, token: str | None, verified: bool
) -> None:
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(
                    "UPDATE organization_branding SET custom_domain = %s, "
                    "custom_domain_token = %s, custom_domain_verified_at = "
                    "CASE WHEN %s THEN now() END WHERE organization_id = %s",
                    (domain, token, verified, ORG_P1),
                )
        finally:
            conn.rollback()


def test_0005_lecture_publique_actives_et_domaines_prouves(migrated_dsn: str) -> None:
    """Sous mulema_app, sans organisation : inconnue, non active, domaine non prouvé = rien."""
    with psycopg.connect(migrated_dsn) as conn:
        try:
            _brand(conn, "p1.fictif.ci", PROOF)
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier("mulema_app")))

            def found(slug: str | None, domain: str | None) -> list[tuple[object, ...]]:
                return conn.execute(
                    "SELECT slug, custom_domain FROM resolve_organization_branding(%s, %s)",
                    (slug, domain),
                ).fetchall()

            assert found("org-p1", None) == [("org-p1", None)]  # domaine non prouvé : caché
            assert found(None, "p1.fictif.ci") == []
            conn.execute("RESET ROLE")
            conn.execute(
                "UPDATE organization_branding SET custom_domain_verified_at = now() "
                "WHERE organization_id = %s",
                (ORG_P1,),
            )
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier("mulema_app")))
            assert found(None, "p1.fictif.ci") == [("org-p1", "p1.fictif.ci")]
            for state in ("integration", "inactive"):
                conn.execute("RESET ROLE")
                conn.execute("UPDATE organizations SET status = %s WHERE id = %s", (state, ORG_P1))
                conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier("mulema_app")))
                assert found("org-p1", None) == found("org-inconnue", None) == []
                assert found(None, "p1.fictif.ci") == []
        finally:
            conn.rollback()


def test_0005_preuve_sans_jeton_refusee_par_la_base(migrated_dsn: str) -> None:
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            _brand(conn, "a.fictif.ci", None)  # domaine d'avant 0005 : sans jeton, admis
            with pytest.raises(psycopg.errors.CheckViolation) as caught:
                conn.execute(
                    "UPDATE organization_branding SET custom_domain_verified_at = now() "
                    "WHERE organization_id = %s",
                    (ORG_P1,),
                )
            assert caught.value.diag.constraint_name == "organization_branding_domain_proof_check"
        finally:
            conn.rollback()


# --- 0006 : import de l'existant (CR-L11-01), additive et rejouable ---------------------------

IMPORT_TABLES = frozenset({"import_runs", "external_ids"})


def test_downgrade_de_0006_refuse(empty_db_dsn: str) -> None:
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "head")
    with pytest.raises(RuntimeError, match="validation humaine"):
        command.downgrade(cfg, "0005")


def test_0006_est_additive(empty_db_dsn: str) -> None:
    """0005 → 0006 : deux tables nouvelles, rien de retiré ni réécrit ailleurs."""
    cfg = _config(empty_db_dsn)
    command.upgrade(cfg, "0005")
    before_columns, before_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    command.upgrade(cfg, "0006")
    after_columns, after_constraints = _catalog(empty_db_dsn), _constraints(empty_db_dsn)
    assert before_columns < after_columns
    assert {c[0] for c in after_columns - before_columns} == IMPORT_TABLES
    assert before_constraints < after_constraints
    assert {c[0] for c in after_constraints - before_constraints} == IMPORT_TABLES


def test_0006_rejouable(empty_db_dsn: str) -> None:
    command.upgrade(_config(empty_db_dsn), "head")
    before = _schema_catalog(empty_db_dsn)
    apply_sql_file(empty_db_dsn, SQL_0006)
    apply_sql_file(empty_db_dsn, SQL_0006)
    assert _schema_catalog(empty_db_dsn) == before


def test_0006_isolation_et_droits_sur_la_base_migree(migrated_dsn: str) -> None:
    """RLS forcée, politique unique ; journal : SELECT/INSERT/UPDATE ; clés : ajout seul."""
    qual = "(organization_id = app_current_organization_id())"
    expected_rights = {
        "import_runs": {"SELECT", "INSERT", "UPDATE"},
        "external_ids": {"SELECT", "INSERT"},
    }
    with psycopg.connect(migrated_dsn) as conn:
        for table, rights in expected_rights.items():
            flags = conn.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = %s::regclass",
                (table,),
            ).fetchone()
            policies = conn.execute(
                "SELECT policyname, cmd, qual, with_check FROM pg_policies WHERE tablename = %s",
                (table,),
            ).fetchall()
            granted = {
                r[0]
                for r in conn.execute(
                    "SELECT privilege_type FROM information_schema.role_table_grants "
                    "WHERE table_name = %s AND grantee = 'mulema_app'",
                    (table,),
                ).fetchall()
            }
            assert flags == (True, True), table
            assert policies == [("tenant_isolation", "ALL", qual, qual)], table
            assert granted == rights, table


def _run(conn: psycopg.Connection, currency: str = "XOF") -> str:
    row = conn.execute(
        "INSERT INTO import_runs (organization_id, source, spec_version, status_map_version, "
        "source_currency) VALUES (%s, 'laravel_2026', 'laravel-2026.1', 'statuts-1', %s) "
        "RETURNING id",
        (ORG_P1, currency),
    ).fetchone()
    assert row is not None
    return str(row[0])


def _member_of(conn: psycopg.Connection) -> str:
    row = conn.execute("SELECT id FROM members WHERE organization_id = %s", (ORG_P1,)).fetchone()
    assert row is not None
    return str(row[0])


def test_0006_devise_de_la_source_egale_a_celle_de_l_organisation(migrated_dsn: str) -> None:
    """MCI01 : une source en XAF ne s'importe jamais dans une organisation en XOF."""
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            _run(conn, "XOF")
            with pytest.raises(psycopg.Error) as caught:
                _run(conn, "XAF")
            assert caught.value.sqlstate == "MCI01"
        finally:
            conn.rollback()


def test_0006_journal_termine_fige(migrated_dsn: str) -> None:
    """MCI02 : un import terminé ne change plus ; un import en cours ne recule pas."""
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            run = _run(conn)
            conn.execute(
                "UPDATE import_runs SET batches_committed = 2 WHERE id = %s", (run,)
            )
            with pytest.raises(psycopg.Error) as backwards:
                conn.execute("UPDATE import_runs SET batches_committed = 1 WHERE id = %s", (run,))
            assert backwards.value.sqlstate == "MCI02"
            conn.rollback()
            _app(conn, ORG_P1)
            run = _run(conn)
            conn.execute(
                "UPDATE import_runs SET status = 'terminee', finished_at = now() WHERE id = %s",
                (run,),
            )
            with pytest.raises(psycopg.Error) as frozen:
                conn.execute("UPDATE import_runs SET rows_inserted = 9 WHERE id = %s", (run,))
            assert frozen.value.sqlstate == "MCI02"
        finally:
            conn.rollback()


@pytest.mark.parametrize(
    ("key_name", "external_key", "kind", "status", "error"),
    [
        ("subscription_number", "subscription_number:SUB-0001", "member", "PENDING_REVIEW", None),
        ("legacy_user_id", "legacy_user_id:42", "member", None, None),
        ("email", "email:fictif@exemple.invalid", "member", None, "external_ids_key_check"),
        ("subscription_number", "autre:SUB-0001", "member", None, "external_ids_key_check"),
        ("subscription_number", "subscription_number:", "member", None, "external_ids_key_check"),
        ("claim_reference", "claim_reference:CLM-1", "member", "PENDING_REVIEW", None),
        ("claim_reference", "claim_reference:CLM-1", "claim", None, "MCI03"),
        ("claim_reference", "claim_reference:CLM-2", "plan", "PENDING_REVIEW", "MCI03"),
    ],
)
def test_0006_cle_d_origine_gardee_par_la_base(
    migrated_dsn: str,
    key_name: str,
    external_key: str,
    kind: str,
    status: str | None,
    error: str | None,
) -> None:
    """Clé préfixée par son nom, jamais une adresse électronique, ligne visée existante."""
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            run, member = _run(conn), _member_of(conn)
            statement = (
                "INSERT INTO external_ids (organization_id, source, kind, key_name, external_key, "
                "one_id, import_run_id, import_status, status_map_version) "
                "VALUES (%s, 'laravel_2026', %s, %s, %s, %s, %s, %s, %s)"
            )
            params = (ORG_P1, kind, key_name, external_key, member, run, status,
                      "statuts-1" if status else None)
            if error is None:
                conn.execute(statement, params)
                return
            with pytest.raises(psycopg.Error) as caught:
                conn.execute(statement, params)
            if error.startswith("MCI"):
                assert caught.value.sqlstate == error
            else:
                assert caught.value.diag.constraint_name == error
        finally:
            conn.rollback()


def test_0006_cles_en_ajout_seul_et_uniques(migrated_dsn: str) -> None:
    """Rejouer la même clé : violation d'unicité ; modifier ou supprimer : refusé (MCL01/42501)."""
    with psycopg.connect(migrated_dsn) as conn:
        _app(conn, ORG_P1)
        try:
            run, member = _run(conn), _member_of(conn)
            insert = (
                "INSERT INTO external_ids (organization_id, source, kind, key_name, external_key, "
                "one_id, import_run_id) VALUES (%s, 'laravel_2026', 'member', 'legacy_user_id', "
                "'legacy_user_id:7', %s, %s)"
            )
            conn.execute(insert, (ORG_P1, member, run))
            conn.execute("SAVEPOINT s")
            with pytest.raises(psycopg.errors.UniqueViolation):
                conn.execute(insert, (ORG_P1, member, run))
            conn.execute("ROLLBACK TO SAVEPOINT s")
            for statement in (
                "UPDATE external_ids SET one_id = one_id",
                "DELETE FROM external_ids",
            ):
                with pytest.raises(psycopg.Error) as caught:
                    conn.execute(statement)
                assert caught.value.sqlstate in {"42501", "MCL01"}
                conn.execute("ROLLBACK TO SAVEPOINT s")
        finally:
            conn.rollback()
