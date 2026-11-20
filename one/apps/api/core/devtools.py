"""Outils de DÉVELOPPEMENT local (``make dev``, ``make up``) — jamais utilisés en production.

    python -m api.core.devtools env        # écrit .env.dev (secrets aléatoires) s'il manque
    python -m api.core.devtools keys       # clé ES256 de l'émetteur de dev + .dev/oidc/jwks.json
    python -m api.core.devtools token --org <uuid> --sub <sujet>   # jeton d'accès de dev
    python -m api.core.devtools provision  # migrations (propriétaire) + rôle de connexion
    python -m api.core.devtools serve      # sans Docker : PostgreSQL 16 embarqué + API

L'émetteur de dev (``https://dev-oidc.mulemacare.invalid``) est refusé par ``api.main`` en
production (TLD ``.invalid``). Les secrets et la clé privée vivent dans ``.env.dev`` et
``.dev/`` (ignorés par git), générés sur le poste ; rien n'est versionné.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

import jwt
import psycopg
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.engine import URL, make_url

from api.integrations.egress import ONE_ROOT

DEV_DIR: Final = ONE_ROOT / ".dev"
OIDC_DIR: Final = DEV_DIR / "oidc"
ENV_FILE: Final = ONE_ROOT / ".env.dev"
ALEMBIC_INI: Final = ONE_ROOT / "alembic.ini"
DEV_ISSUER: Final = "https://dev-oidc.mulemacare.invalid"
DEV_AUDIENCE: Final = "mulemacare-one-api"
DEV_KID: Final = "dev-es256"
LOGIN_ROLE: Final = "mulema_api"
DEMO_ORG: Final = "00000000-0000-4000-8000-000000000001"  # organisation du jeu de démo
_SECRETS: Final = (
    "MULEMA_CARD_KEY",
    "MULEMA_METRICS_PSEUDONYM_KEY",
    "MULEMA_PAYMENT_LINK_SECRET",
    "MULEMA_PAYMENT_SECRET_WAVE",
)


def write_env(path: Path = ENV_FILE) -> bool:
    """Écrit ``.env.dev`` avec des secrets ALÉATOIRES s'il n'existe pas (jamais écrasé)."""
    if path.exists():
        return False
    lines = [
        "# Généré par `python -m api.core.devtools env` — poste de dev uniquement, non versionné.",
        "MULEMA_ENV=development",
        "MULEMA_EXPOSE_DOCS=1",
        "MULEMA_COUNTRY=CI",
        *(f"{name}={secrets.token_hex(32)}" for name in _SECRETS),
        "MULEMA_PAYMENT_PUBLIC_BASE_URL=https://payer.mulemacare.invalid/p",
        f"MULEMA_OIDC_ISSUER={DEV_ISSUER}",
        f"MULEMA_OIDC_AUDIENCE={DEV_AUDIENCE}",
        f"MULEMA_DEV_OWNER_PASSWORD={secrets.token_hex(16)}",
        f"MULEMA_DEV_LOGIN_PASSWORD={secrets.token_hex(16)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return True


def read_env(path: Path = ENV_FILE) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def write_keys(directory: Path = OIDC_DIR) -> Path:
    """Clé privée ES256 de l'émetteur de dev (0600) et JWKS public ; conservées si présentes."""
    directory.mkdir(parents=True, exist_ok=True)
    private_path = directory / "dev-issuer.pem"
    jwks_path = directory / "jwks.json"
    if not private_path.exists():
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        private_path.write_bytes(pem)
        private_path.chmod(0o600)
    private = _private_key(private_path)
    jwk = ECAlgorithm.to_jwk(private.public_key(), as_dict=True)
    jwks = {"keys": [jwk | {"kid": DEV_KID, "use": "sig", "alg": "ES256"}]}
    jwks_path.write_text(json.dumps(jwks, indent=2) + "\n", encoding="utf-8")
    return jwks_path


def _private_key(path: Path) -> ec.EllipticCurvePrivateKey:
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        msg = "clé de l'émetteur de dev inattendue (EC P-256 attendue)"
        raise TypeError(msg)
    return key


def mint_token(organization: str, subject: str, ttl: int, directory: Path = OIDC_DIR) -> str:
    """Jeton d'accès de DEV signé par la clé locale (organisation = UUID du jeton One)."""
    now = int(time.time())
    payload = {
        "iss": DEV_ISSUER,
        "aud": DEV_AUDIENCE,
        "sub": subject,
        "iat": now,
        "exp": now + ttl,
        "mulema_org": str(uuid.UUID(organization)),
    }
    key = _private_key(directory / "dev-issuer.pem")
    return jwt.encode(payload, key, algorithm="ES256", headers={"kid": DEV_KID})


def provision(owner_url: str, login_password: str, *, login_role: str = LOGIN_ROLE) -> None:
    """Migrations en propriétaire, puis rôle de CONNEXION membre de ``mulema_app`` et droit de
    lecture de ``alembic_version`` (CR-L10-02). Ce que l'exploitation fait en production."""
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", owner_url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    url = make_url(owner_url)
    conninfo = {
        "host": url.host or url.query.get("host"),
        "port": url.port or url.query.get("port"),
        "dbname": url.database,
        "user": url.username,
        "password": url.password,
    }
    params = {k: str(v) for k, v in conninfo.items() if v}
    with psycopg.connect(**params, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (login_role,)).fetchone()
        verb = "ALTER" if exists else "CREATE"
        conn.execute(
            sql.SQL(
                verb + " ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE PASSWORD {}"
            ).format(sql.Identifier(login_role), sql.Literal(login_password))
        )
        conn.execute(sql.SQL("GRANT mulema_app TO {}").format(sql.Identifier(login_role)))
        conn.execute("GRANT SELECT ON alembic_version TO mulema_app")


def _serve(env: Mapping[str, str], jwks: Path) -> int:
    """Mode sans Docker : PostgreSQL 16 embarqué (pgserver, dépendance de dev) dans .dev/."""
    from pgserver.postgres_server import get_server  # noqa: PLC0415 — dépendance de dev

    server = get_server(DEV_DIR / "pgdata", cleanup_mode=None)
    params = {k: str(v) for k, v in conninfo_to_dict(server.get_uri()).items() if v is not None}
    with psycopg.connect(**params, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = 'insurance'").fetchone():
            conn.execute("CREATE DATABASE insurance")

    def url(user: str, password: str | None) -> str:
        query = {"host": params["host"], "port": params.get("port", "5432")}
        return URL.create(
            "postgresql+psycopg",
            username=user,
            password=password,
            database="insurance",
            query=query,
        ).render_as_string(hide_password=False)

    provision(url(params.get("user", "postgres"), None), env["MULEMA_DEV_LOGIN_PASSWORD"])
    child = (
        dict(os.environ)
        | dict(env)
        | {
            "MULEMA_INSURANCE_DATABASE_URL": url(LOGIN_ROLE, env["MULEMA_DEV_LOGIN_PASSWORD"]),
            "MULEMA_OIDC_JWKS_FILE": str(jwks),
            "PYTHONPATH": str(ONE_ROOT / "apps"),
        }
    )
    return subprocess.call([sys.executable, "-m", "api.main"], env=child, cwd=ONE_ROOT)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.core.devtools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("env")
    sub.add_parser("keys")
    token = sub.add_parser("token")
    token.add_argument("--org", default=DEMO_ORG)
    token.add_argument("--sub", required=True)
    token.add_argument("--ttl", type=int, default=3600)
    sub.add_parser("provision")
    sub.add_parser("serve")
    args = parser.parse_args(argv)
    if args.command == "env":
        print("écrit" if write_env() else "présent", ENV_FILE)
    elif args.command == "keys":
        print(write_keys())
    elif args.command == "token":
        print(mint_token(args.org, args.sub, args.ttl))
    elif args.command == "provision":
        provision(
            os.environ["MULEMA_MIGRATION_DATABASE_URL"], os.environ["MULEMA_DEV_LOGIN_PASSWORD"]
        )
    else:
        write_env()
        return _serve(read_env(), write_keys())
    return 0


if __name__ == "__main__":
    sys.exit(main())
