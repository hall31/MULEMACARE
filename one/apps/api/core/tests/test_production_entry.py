"""L10 — point d'entrée de production (``api.main``) : configuration en échec fermé, rôle de
connexion vérifié, documentation fermée en production, sondes, identité OIDC réelle de bout en
bout et arrêt propre d'un vrai serveur uvicorn.

Base : chaîne Alembic complète (``upgrade head``) en propriétaire, puis un rôle de CONNEXION
dédié, membre de ``mulema_app`` (ce que l'exploitation crée, schema.sql §Rôle applicatif). Clés
OIDC, secrets et jetons générés à chaque exécution ; données fictives.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL

from api.core.database import IsolationNotEnforcedError
from api.core.settings import ConfigurationError
from api.core.tests.oidc_keys import AUDIENCE, ISSUER, SigningKey, claims, ec_key, sign
from api.main import build_app
from api.tests.paths import ALEMBIC_INI, ONE_ROOT

ORG = uuid.UUID("00000000-0000-4000-8000-00000000c1a0")
SUBJECT = "sub-oidc-gestionnaire"
FIXTURE = ONE_ROOT / "apps" / "api" / "tests" / "contracts" / "fixtures" / "one_row_per_table.sql"
OK, UNAUTHORIZED, NOT_FOUND, UNAVAILABLE = 200, 401, 404, 503
EXIT_CONFIGURATION = 78


def _url(dsn: str, *, user: str | None = None, password: str | None = None) -> str:
    params = {k: str(v) for k, v in conninfo_to_dict(dsn).items() if v is not None}
    database = params.pop("dbname")
    default_user = params.pop("user", None)
    default_password = params.pop("password", None)
    return URL.create(
        "postgresql+psycopg",
        username=user or default_user,
        password=password if user else default_password,
        database=database,
        query=params,
    ).render_as_string(hide_password=False)


def _migrate(dsn: str, revision: str = "head") -> None:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", _url(dsn).replace("%", "%%"))
    command.upgrade(cfg, revision)


@dataclass
class Instance:
    owner_dsn: str
    login_url: str
    superuser_url: str
    jwks: Path
    key: SigningKey

    def env(self, **overrides: str) -> dict[str, str]:
        base = {
            "MULEMA_ENV": "production",
            "MULEMA_COUNTRY": "CI",
            "MULEMA_INSURANCE_DATABASE_URL": self.login_url,
            "MULEMA_DB_APP_ROLE": "mulema_app",
            "MULEMA_CARD_KEY": secrets.token_hex(32),
            "MULEMA_METRICS_PSEUDONYM_KEY": secrets.token_hex(32),
            "MULEMA_PAYMENT_LINK_SECRET": secrets.token_hex(32),
            "MULEMA_PAYMENT_PUBLIC_BASE_URL": "https://payer.mulemacare.example/p",
            "MULEMA_OIDC_ISSUER": "https://idp.mulemacare.example/realms/one",
            "MULEMA_OIDC_AUDIENCE": AUDIENCE,
            "MULEMA_OIDC_JWKS_FILE": str(self.jwks),
        }
        return base | overrides

    def token(self, subject: str = SUBJECT, **extra: object) -> str:
        payload = claims(subject, ORG, iss="https://idp.mulemacare.example/realms/one") | extra
        return sign(self.key, payload)


def _role(admin: psycopg.Connection, name: str, password: str, options: str = "") -> None:
    admin.execute(
        sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} " + options).format(
            sql.Identifier(name), sql.Literal(password)
        )
    )
    admin.execute(sql.SQL("GRANT mulema_app TO {}").format(sql.Identifier(name)))


@pytest.fixture(scope="module")
def instance(pg_server_dsn: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Instance]:
    name = f"prod_entry_{uuid.uuid4().hex[:10]}"
    login = f"one_api_{uuid.uuid4().hex[:8]}"
    password = secrets.token_hex(16)
    with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(pg_server_dsn, dbname=name)
    try:
        _migrate(dsn)
        with psycopg.connect(dsn, autocommit=True) as admin:
            _role(admin, login, password)
            # Étape d'exploitation (CR-L10-02) : /readyz lit la révision sous mulema_app.
            admin.execute("GRANT SELECT ON alembic_version TO mulema_app")
            script = FIXTURE.read_text(encoding="utf-8")
            admin.execute(
                script.replace("__ORG__", str(ORG)).replace("__SLUG__", "org-oidc").encode()
            )
            admin.execute("SELECT set_config('app.organization_id', %s, false)", (str(ORG),))
            user = admin.execute(
                "INSERT INTO users (organization_id, idp_subject, display_name) "
                "VALUES (%s, %s, 'Agent fictif OIDC') RETURNING id",
                (ORG, SUBJECT),
            ).fetchone()
            assert user is not None
            admin.execute(
                "INSERT INTO user_roles (organization_id, user_id, role) "
                "VALUES (%s, %s, 'gestionnaire')",
                (ORG, user[0]),
            )
        key = ec_key()
        jwks = tmp_path_factory.mktemp("oidc") / "jwks.json"
        jwks.write_text(json.dumps({"keys": [key.public_jwk()]}), encoding="utf-8")
        yield Instance(
            owner_dsn=dsn,
            login_url=_url(dsn, user=login, password=password),
            superuser_url=_url(dsn),
            jwks=jwks,
            key=key,
        )
    finally:
        with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login)))


# --- Configuration : échec fermé, sans valeur secrète dans le message --------------------------

REQUIRED = [
    "MULEMA_INSURANCE_DATABASE_URL",
    "MULEMA_COUNTRY",
    "MULEMA_CARD_KEY",
    "MULEMA_METRICS_PSEUDONYM_KEY",
    "MULEMA_PAYMENT_LINK_SECRET",
    "MULEMA_PAYMENT_PUBLIC_BASE_URL",
    "MULEMA_OIDC_ISSUER",
    "MULEMA_OIDC_AUDIENCE",
]


@pytest.mark.parametrize("missing", REQUIRED)
def test_variable_obligatoire_absente_refuse_le_demarrage(instance: Instance, missing: str) -> None:
    env = instance.env()
    del env[missing]
    with pytest.raises(ConfigurationError, match=missing):
        build_app(env)


@pytest.mark.parametrize(
    "secret_name",
    ["MULEMA_CARD_KEY", "MULEMA_METRICS_PSEUDONYM_KEY", "MULEMA_PAYMENT_LINK_SECRET"],
)
def test_secret_trop_court_refuse_sans_divulguer_sa_valeur(
    instance: Instance, secret_name: str
) -> None:
    short = secrets.token_hex(16)
    with pytest.raises(ConfigurationError, match=secret_name) as caught:
        build_app(instance.env(**{secret_name: short}))
    assert short not in str(caught.value)


def test_role_applicatif_vide_refuse_en_production(instance: Instance) -> None:
    with pytest.raises(ConfigurationError, match="MULEMA_DB_APP_ROLE"):
        build_app(instance.env(MULEMA_DB_APP_ROLE=""))


def test_jwks_hors_liste_blanche_refuse(instance: Instance) -> None:
    env = instance.env(MULEMA_OIDC_JWKS_URL="https://idp.ailleurs.example/jwks")
    del env["MULEMA_OIDC_JWKS_FILE"]
    with pytest.raises(ConfigurationError, match="liste blanche"):
        build_app(env)


def test_jwks_url_et_fichier_exclusifs(instance: Instance) -> None:
    env = instance.env(MULEMA_OIDC_JWKS_URL="https://healthos.ci.mulemacare.internal/jwks")
    with pytest.raises(ConfigurationError, match="exactement"):
        build_app(env)


@pytest.mark.parametrize(
    "issuer", ["http://idp.mulemacare.example", "https://idp.mulemacare.invalid/realms/dev"]
)
def test_emetteur_de_developpement_refuse_en_production(instance: Instance, issuer: str) -> None:
    with pytest.raises(ConfigurationError, match="MULEMA_OIDC_ISSUER"):
        build_app(instance.env(MULEMA_OIDC_ISSUER=issuer))


def test_algorithme_hmac_refuse_par_la_configuration(instance: Instance) -> None:
    with pytest.raises(ConfigurationError, match="MULEMA_OIDC"):
        build_app(instance.env(MULEMA_OIDC_ALGORITHMS="RS256,HS256"))


def test_documentation_interdite_en_production(instance: Instance) -> None:
    with pytest.raises(ConfigurationError, match="MULEMA_EXPOSE_DOCS"):
        build_app(instance.env(MULEMA_EXPOSE_DOCS="1"))


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_documentation_absente_en_production(instance: Instance, path: str) -> None:
    client = TestClient(build_app(instance.env()))  # sans démarrage : table de routage seule
    assert client.get(path).status_code == NOT_FOUND


def test_documentation_activable_en_developpement(instance: Instance) -> None:
    app = build_app(
        instance.env(
            MULEMA_ENV="development",
            MULEMA_EXPOSE_DOCS="1",
            MULEMA_OIDC_ISSUER=ISSUER,
        )
    )
    client = TestClient(app)
    assert client.get("/openapi.json").status_code == OK
    assert client.get("/docs").status_code == OK


# --- Démarrage sur une vraie base : rôle de connexion ------------------------------------------


def test_demarrage_refuse_sous_un_superutilisateur(instance: Instance) -> None:
    app = build_app(instance.env(MULEMA_INSURANCE_DATABASE_URL=instance.superuser_url))
    with pytest.raises(IsolationNotEnforcedError, match="connexion"), TestClient(app):
        pass


@pytest.mark.parametrize(
    "privilege", ["BYPASSRLS", "OWNER"], ids=["bypassrls", "proprietaire_d_une_table"]
)
def test_demarrage_refuse_si_le_role_de_connexion_contourne_la_rls(
    instance: Instance, pg_server_dsn: str, privilege: str
) -> None:
    name = f"one_bad_{uuid.uuid4().hex[:8]}"
    password = secrets.token_hex(16)
    try:
        with psycopg.connect(instance.owner_dsn, autocommit=True) as admin:
            _role(admin, name, password, "BYPASSRLS" if privilege == "BYPASSRLS" else "")
            if privilege == "OWNER":
                admin.execute(
                    sql.SQL("ALTER TABLE outbound_messages OWNER TO {}").format(
                        sql.Identifier(name)
                    )
                )
        url = _url(instance.owner_dsn, user=name, password=password)
        app = build_app(instance.env(MULEMA_INSURANCE_DATABASE_URL=url))
        with pytest.raises(IsolationNotEnforcedError), TestClient(app):
            pass
    finally:
        with psycopg.connect(instance.owner_dsn, autocommit=True) as admin:
            owner = conninfo_to_dict(pg_server_dsn).get("user") or "postgres"
            admin.execute(
                sql.SQL("REASSIGN OWNED BY {} TO {}").format(
                    sql.Identifier(name), sql.Identifier(str(owner))
                )
            )
            admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(name)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))


@pytest.fixture
def client(instance: Instance) -> Iterator[TestClient]:
    # Portée « test » : l'application démarrée empile la garde d'egress du pays CI (sans boucle
    # locale) ; elle doit être arrêtée avant les tests du vrai serveur sur 127.0.0.1.
    with TestClient(build_app(instance.env())) as test_client:
        yield test_client


def test_sondes_vivacite_et_preparation(client: TestClient) -> None:
    live = client.get("/healthz")
    assert (live.status_code, live.json()) == (OK, {"status": "ok"})
    ready = client.get("/readyz")
    assert ready.status_code == OK
    assert ready.json() == {"status": "pret", "checks": {"base": "ok", "migrations": "a_jour"}}
    assert ready.headers["cache-control"] == "no-store"


def test_identite_oidc_de_bout_en_bout(client: TestClient, instance: Instance) -> None:
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {instance.token()}"})
    assert me.status_code == OK, me.text
    unknown = client.get(
        "/v1/me", headers={"Authorization": f"Bearer {instance.token('sub-inconnu')}"}
    )
    assert unknown.status_code == UNAUTHORIZED
    assert unknown.json()["code"] == "AUTH-01"
    other_key = sign(ec_key(instance.key.kid), claims(SUBJECT, ORG))
    forged = client.get("/v1/me", headers={"Authorization": f"Bearer {other_key}"})
    assert forged.status_code == UNAUTHORIZED


def test_preparation_illisible_sans_droit_sur_alembic_version(
    instance: Instance, pg_server_dsn: str
) -> None:
    del pg_server_dsn
    with psycopg.connect(instance.owner_dsn, autocommit=True) as admin:
        admin.execute("REVOKE SELECT ON alembic_version FROM mulema_app")
    try:
        with TestClient(build_app(instance.env())) as test_client:
            ready = test_client.get("/readyz")
        assert ready.status_code == UNAVAILABLE
        assert ready.json()["checks"]["migrations"] == "illisible"
    finally:
        with psycopg.connect(instance.owner_dsn, autocommit=True) as admin:
            admin.execute("GRANT SELECT ON alembic_version TO mulema_app")


def test_preparation_en_retard_si_une_migration_manque(instance: Instance) -> None:
    with psycopg.connect(instance.owner_dsn, autocommit=True) as admin:
        (current,) = admin.execute("SELECT version_num FROM alembic_version").fetchone() or ("",)
        admin.execute("UPDATE alembic_version SET version_num = '0001'")
    try:
        with TestClient(build_app(instance.env())) as test_client:
            ready = test_client.get("/readyz")
        assert ready.status_code == UNAVAILABLE
        assert ready.json() == {
            "status": "indisponible",
            "checks": {"base": "ok", "migrations": "en_retard"},
        }
    finally:
        with psycopg.connect(instance.owner_dsn, autocommit=True) as admin:
            admin.execute("UPDATE alembic_version SET version_num = %s", (current,))


# --- Vrai serveur : python -m api.main ---------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def _spawn(env: dict[str, str]) -> subprocess.Popen[str]:
    child_env = {k: v for k, v in os.environ.items() if not k.startswith("MULEMA_")}
    child_env |= env | {"PYTHONPATH": str(ONE_ROOT / "apps")}
    return subprocess.Popen(
        [sys.executable, "-m", "api.main"],
        env=child_env,
        cwd=ONE_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_ready(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            pytest.fail(f"serveur arrêté au démarrage : {output}")
        try:
            if httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1).status_code == OK:
                return
        except httpx.TransportError:
            time.sleep(0.2)
    pytest.fail("serveur non prêt en 30 s")


def test_serveur_reel_demarre_sert_et_s_arrete_proprement(instance: Instance) -> None:
    port = _free_port()
    process = _spawn(instance.env(MULEMA_HTTP_PORT=str(port)))
    try:
        _wait_ready(port, process)
        ready = httpx.get(f"http://127.0.0.1:{port}/readyz", timeout=5)
        assert ready.status_code == OK
        assert "server" not in ready.headers
        assert httpx.get(f"http://127.0.0.1:{port}/docs", timeout=5).status_code == NOT_FOUND
        process.send_signal(signal.SIGTERM)
        output, _ = process.communicate(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
    # uvicorn termine proprement PUIS relève le signal reçu (code -SIGTERM) : la preuve de
    # l'arrêt propre est la fin du cycle de vie (base libérée, « app.stopped » en dernier).
    assert process.returncode in {0, -signal.SIGTERM}, output
    events = [json.loads(line)["event"] for line in output.splitlines() if line.startswith("{")]
    assert "app.started" in events
    assert events[-1] == "app.stopped"


def test_serveur_reel_refuse_un_superutilisateur(instance: Instance) -> None:
    process = _spawn(
        instance.env(
            MULEMA_INSURANCE_DATABASE_URL=instance.superuser_url,
            MULEMA_HTTP_PORT=str(_free_port()),
        )
    )
    output, _ = process.communicate(timeout=60)
    assert process.returncode != 0
    assert '"event": "startup.refused"' in output


def test_serveur_reel_configuration_incomplete(instance: Instance) -> None:
    env = instance.env()
    del env["MULEMA_CARD_KEY"]
    process = _spawn(env)
    output, _ = process.communicate(timeout=60)
    assert process.returncode == EXIT_CONFIGURATION
    assert "MULEMA_CARD_KEY" in output
    assert env["MULEMA_PAYMENT_LINK_SECRET"] not in output
