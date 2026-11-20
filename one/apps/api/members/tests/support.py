"""Environnement de test du lot L4 : vraie API, vraie base, rôle ``mulema_app``.

- Base PostgreSQL 16 dédiée au module, schéma du contrat appliqué tel quel.
- Deux organisations fictives A et B, chacune avec : un utilisateur par rôle, la règle R-01
  (paramètres du prototype : statut actif, suspension à J+45) et une formule en vigueur.
- L'API est construite par ``create_app`` du noyau (SET LOCAL ROLE mulema_app, RLS forcée),
  avec les routes L4 montées et une horloge fixe pilotée par le test.
- Les canaux de paiement sont les implémentations SIMULÉES (secrets aléatoires par test).
- Toute donnée est fictive.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL

from api.core.app import create_app
from api.core.database import Database
from api.core.identity import Identity, InMemoryIdentityProvider
from api.core.settings import Settings
from api.integrations.egress import ALLOWLIST_PATH, egress_guard, load_allowlist
from api.ledger.accounts import CHART_OF_ACCOUNTS
from api.members.cards import CardKeys
from api.members.routes import MembersRuntime
from api.members.routes import install as install_members
from api.payments.channels import ChannelRegistry, SimulatedChannel
from api.payments.config import PaymentsConfig
from api.payments.routes import PaymentsRuntime
from api.payments.routes import install as install_payments
from api.tests.contracts.helpers import APP_ROLE, apply_sql_file
from api.tests.paths import EVENTS_MD, SCHEMA_SQL

ROLES = ("gestionnaire", "admin", "medecin_conseil", "clinique")
SIMULATED = ("wave", "orange_money", "mtn_momo")
START = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
R01_PARAMS = {"statuts_ouvrant_droits": ["actif"], "suspension_apres_jours_impayes": 45}
PUBLIC_BASE_URL = "https://payer.mulemacare.invalid/p"


def sqlalchemy_url(conninfo: str) -> str:
    """DSN libpq (clé=valeur ou URI) → URL SQLAlchemy pour psycopg async."""
    params = {k: str(v) for k, v in conninfo_to_dict(conninfo).items() if v is not None}
    database = params.pop("dbname")
    user = params.pop("user", None)
    password = params.pop("password", None)
    url = URL.create(
        "postgresql+psycopg", username=user, password=password, database=database, query=params
    )
    return url.render_as_string(hide_password=False)


class FixedClock:
    """Horloge pilotée par le test (UTC ; Abidjan est à UTC+0 sans heure d'été)."""

    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def set_day(self, day: date, hour: int = 9) -> None:
        self.current = datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)

    def advance(self, delta: timedelta) -> None:
        self.current += delta

    def today(self) -> date:
        return self.current.date()


@dataclass
class OrgFixture:
    key: str
    id: UUID
    slug: str
    plan_code: str
    provider_id: UUID
    users: dict[str, UUID] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)


@dataclass
class L4Env:
    dsn: str
    client: TestClient
    clock: FixedClock
    channels: ChannelRegistry
    orgs: dict[str, OrgFixture]

    def auth(self, org: str, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.orgs[org].tokens[role]}"}

    def headers(self, org: str, role: str, key: str | None = None) -> dict[str, str]:
        return {**self.auth(org, role), "Idempotency-Key": key or f"cle-{uuid.uuid4().hex}"}

    @property
    def database(self) -> Database:
        database: Database = self.client.app.state.database  # type: ignore[attr-defined]
        return database

    def run[T](self, func: Callable[..., Awaitable[T]], *args: Any) -> T:  # noqa: ANN401
        """Exécute une coroutine dans la boucle de l'application (même pool de connexions)."""
        portal = self.client.portal
        assert portal is not None
        return portal.call(func, *args)

    def simulated(self, channel: str) -> SimulatedChannel:
        found = self.channels.get(channel)
        assert isinstance(found, SimulatedChannel)
        return found

    def rows(self, query: str, params: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
        """Lecture en propriétaire (superutilisateur, hors RLS) pour les assertions."""
        with psycopg.connect(self.dsn) as conn:
            return list(conn.execute(query.encode(), params).fetchall())

    def scalar(self, query: str, params: tuple[object, ...] = ()) -> Any:  # noqa: ANN401
        found = self.rows(query, params)
        assert len(found) == 1
        return found[0][0]


def _one(conn: psycopg.Connection, query: str, params: tuple[object, ...]) -> UUID:
    row = conn.execute(query.encode(), params).fetchone()
    assert row is not None
    assert isinstance(row[0], UUID)
    return row[0]


def seed_organization(dsn: str, key: str, idp: InMemoryIdentityProvider) -> OrgFixture:
    """Organisation fictive prête pour L4 (paramétrage posé par le propriétaire)."""
    slug = f"l4-{key}-{uuid.uuid4().hex[:8]}"
    with psycopg.connect(dsn) as conn:
        org = _one(
            conn,
            "INSERT INTO organizations (slug, name, country_code, timezone, capabilities) "
            "VALUES (%s, %s, 'CI', 'Africa/Abidjan', ARRAY['porteur_de_risque', 'gestionnaire']) "
            "RETURNING id",
            (slug, f"Mutuelle fictive {key}"),
        )
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(org),))
        provider = _one(
            conn,
            "INSERT INTO providers (organization_id, name, kind, city, country_code) "
            "VALUES (%s, 'Clinique fictive', 'clinique', 'Abidjan', 'CI') RETURNING id",
            (org,),
        )
        rule = _one(
            conn,
            "INSERT INTO rules (organization_id, code, label, kind) "
            "VALUES (%s, 'R-01', 'Droits ouverts', 'droits') RETURNING id",
            (org,),
        )
        conn.execute(
            "INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, params, "
            "state) VALUES (%s, %s, 1, DATE '2020-01-01', %s, 'en_vigueur')",
            (org, rule, json.dumps(R01_PARAMS)),
        )
        plan = _one(
            conn,
            "INSERT INTO plans (organization_id, code, name) "
            "VALUES (%s, 'FORMULE-T', 'Formule test') RETURNING id",
            (org,),
        )
        conn.execute(
            "INSERT INTO plan_versions (organization_id, plan_id, version, valid_from, state, "
            "coverage_rate_bp, family_annual_ceiling_xof, waiting_period_days, "
            "monthly_contribution_xof) "
            "VALUES (%s, %s, 1, DATE '2020-01-01', 'en_vigueur', 8000, 3000000, 60, 27500)",
            (org, plan),
        )
        for account in CHART_OF_ACCOUNTS:
            conn.execute(
                "INSERT INTO ledger_accounts (organization_id, code, label, account_class) "
                "VALUES (%s, %s, %s, %s)",
                (org, account.code, account.label, account.account_class),
            )
        fixture = OrgFixture(
            key=key, id=org, slug=slug, plan_code="FORMULE-T", provider_id=provider
        )
        for role in ROLES:
            subject = f"sub-{key}-{role}-{uuid.uuid4().hex[:8]}"
            user = _one(
                conn,
                "INSERT INTO users (organization_id, idp_subject, display_name) "
                "VALUES (%s, %s, %s) RETURNING id",
                (org, subject, f"Agent fictif {role}"),
            )
            conn.execute(
                "INSERT INTO user_roles (organization_id, user_id, role, provider_id) "
                "VALUES (%s, %s, %s, %s)",
                (org, user, role, provider if role == "clinique" else None),
            )
            fixture.users[role] = user
            fixture.tokens[role] = idp.issue(Identity(subject=subject, organization_id=org))
    return fixture


def build_registry() -> ChannelRegistry:
    return ChannelRegistry(
        [SimulatedChannel(name, uuid.uuid4().bytes + uuid.uuid4().bytes) for name in SIMULATED]
    )


@dataclass
class PreparedDatabase:
    dsn: str
    orgs: dict[str, OrgFixture]
    idp: InMemoryIdentityProvider


def create_database(admin_dsn: str, prefix: str) -> str:
    name = f"{prefix}_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return make_conninfo(admin_dsn, dbname=name)


def drop_database(admin_dsn: str, dsn: str) -> None:
    name = conninfo_to_dict(dsn)["dbname"]
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(str(name)))
        )


@pytest.fixture(scope="module")
def l4_env(pg_server_dsn: str) -> Iterator[L4Env]:
    dsn = create_database(pg_server_dsn, "l4_test")
    try:
        apply_sql_file(dsn, SCHEMA_SQL)
        idp = InMemoryIdentityProvider()
        orgs = {key: seed_organization(dsn, key, idp) for key in ("a", "b")}
        with start_client(dsn, idp, orgs) as env:
            yield env
    finally:
        drop_database(pg_server_dsn, dsn)


class start_client:  # noqa: N801 — gestionnaire de contexte au nom d'action
    """Construit l'application L4 complète et la démarre (lifespan : pool + contrôle RLS)."""

    def __init__(
        self, dsn: str, idp: InMemoryIdentityProvider, orgs: dict[str, OrgFixture]
    ) -> None:
        self.dsn, self.idp, self.orgs = dsn, idp, orgs
        self.clock = FixedClock(START)
        self.channels = build_registry()
        app = create_app(
            Settings(database_url=sqlalchemy_url(dsn), app_role=APP_ROLE),
            identity_provider=idp,
        )
        install_members(
            app, MembersRuntime(clock=self.clock, card_keys=CardKeys(uuid.uuid4().bytes * 2))
        )
        install_payments(
            app,
            PaymentsRuntime(
                clock=self.clock,
                config=PaymentsConfig(
                    link_secret=uuid.uuid4().bytes * 2,
                    public_base_url=PUBLIC_BASE_URL,
                    channels=self.channels,
                ),
            ),
        )
        self.client = TestClient(app)

    def __enter__(self) -> L4Env:
        self.client.__enter__()
        return L4Env(self.dsn, self.client, self.clock, self.channels, self.orgs)

    def __exit__(self, *exc: object) -> None:
        self.client.__exit__(*exc)


@pytest.fixture
def guarded(l4_env: L4Env) -> Iterator[L4Env]:
    """R9 : tout le test tourne sous la garde d'egress de la liste blanche CI.

    Les canaux SIMULÉS ne doivent ouvrir aucune connexion réseau : un appel sortant ferait
    échouer le test (EgressDeniedError). La base de test passe par une socket Unix locale.
    """
    with egress_guard(load_allowlist(ALLOWLIST_PATH, country="CI")):
        yield l4_env


# --- Parcours d'API réutilisables ----------------------------------------------------------


def enroll(env: L4Env, org: str, enrolled_on: date, **overrides: str | None) -> dict[str, Any]:
    """Adhésion par l'API ; ``given``, ``family``, ``phone`` (None = sans téléphone)."""
    given = overrides.get("given") or "Awa"
    family = overrides.get("family") or "Koné"
    phone = overrides.get("phone", "+2250700000001")
    holder: dict[str, Any] = {
        "given_name": given,
        "family_name": family,
        "birth_date": "1990-05-12",
    }
    if phone is not None:
        holder["phone_e164"] = phone
    response = env.client.post(
        "/v1/members",
        json={
            "holder": holder,
            "plan_code": env.orgs[org].plan_code,
            "enrolled_on": enrolled_on.isoformat(),
        },
        headers=env.headers(org, "gestionnaire"),
    )
    assert response.status_code == 201, response.text
    member: dict[str, Any] = response.json()
    return member


def run_daily(env: L4Env, org: str) -> Any:  # noqa: ANN401
    from api.members.jobs import run_daily as job  # noqa: PLC0415 — import tardif, module testé

    return env.run(job, env.database, env.orgs[org].id, env.clock.now())


def issue_month(env: L4Env, org: str, period_start: date) -> int:
    from api.payments.jobs import issue_month as job  # noqa: PLC0415

    return env.run(job, env.database, env.orgs[org].id, period_start, env.clock.now())


def active_member(env: L4Env, org: str, **kwargs: str | None) -> dict[str, Any]:
    """Adhérent dont la carence est écoulée, passé « actif » par le traitement quotidien."""
    member = enroll(env, org, env.clock.today() - timedelta(days=90), **kwargs)
    run_daily(env, org)
    status = env.scalar("SELECT status FROM members WHERE id = %s", (UUID(member["id"]),))
    assert status == "actif"
    return member


def contribution_of(env: L4Env, member_id: str, period_start: date) -> UUID:
    found = env.scalar(
        "SELECT id FROM contributions WHERE member_id = %s AND period_start = %s",
        (UUID(member_id), period_start),
    )
    assert isinstance(found, UUID)
    return found


def suspended_member(env: L4Env, org: str) -> tuple[dict[str, Any], UUID]:
    """Adhérent actif dont la cotisation du mois reste impayée 45 jours : suspendu."""
    env.clock.set_day(date(2026, 10, 1))
    member = active_member(env, org)
    period = date(2026, 10, 1)
    issue_month(env, org, period)
    contribution = contribution_of(env, member["id"], period)
    env.clock.set_day(date(2026, 11, 15))  # due_on 01/10 + 45 jours
    run_daily(env, org)
    status = env.scalar("SELECT status FROM members WHERE id = %s", (UUID(member["id"]),))
    assert status == "suspendu"
    return member, contribution


def payment_link_token(env: L4Env, org: str, contribution: UUID) -> str:
    response = env.client.post(
        f"/v1/contributions/{contribution}/payment-links",
        headers=env.headers(org, "gestionnaire"),
    )
    assert response.status_code == 201, response.text
    url = response.json()["url"]
    assert url.startswith(PUBLIC_BASE_URL + "/")
    return str(url.rsplit("/", 1)[1])


def checkout(env: L4Env, token: str, channel: str = "wave") -> UUID:
    response = env.client.post(
        f"/v1/public/payment-links/{token}/checkout",
        json={"channel": channel, "payer_country_code": "FR"},
        headers={"Idempotency-Key": f"cle-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "en_attente"
    return UUID(response.json()["payment_id"])


def hook(slug: str, channel: str) -> str:
    """Chemin du webhook d'une organisation et d'un canal."""
    return f"/v1/webhooks/{slug}/payments/{channel}"


def post_webhook(env: L4Env, path: str, body: bytes, signature: str | None) -> Any:  # noqa: ANN401
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Signature"] = signature
    return env.client.post(path, content=body, headers=headers)


def events(env: L4Env, event_type: str, **payload_filter: str) -> list[dict[str, Any]]:
    """Événements de l'outbox (lecture propriétaire), filtrés sur des champs du payload."""
    found = env.rows(
        "SELECT id, organization_id, event_version, occurred_at, payload, published_at "
        "FROM outbox_events WHERE event_type = %s ORDER BY occurred_at, id",
        (event_type,),
    )
    out = []
    for event_id, org, version, occurred_at, payload, published_at in found:
        if all(payload.get(k) == v for k, v in payload_filter.items()):
            out.append(
                {
                    "event_id": event_id,
                    "organization_id": org,
                    "event_version": version,
                    "occurred_at": occurred_at,
                    "payload": payload,
                    "published_at": published_at,
                }
            )
    return out


# --- Vérification minimale des payloads contre specs/events.md ------------------------------

_JSON_BLOCK = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _payload_schema(event_type: str) -> dict[str, Any]:
    for block in _JSON_BLOCK.findall(EVENTS_MD.read_text(encoding="utf-8")):
        doc = json.loads(block)
        if doc.get("title") == event_type:
            schema: dict[str, Any] = doc["properties"]["payload"]
            return schema
    raise AssertionError(event_type)


def _check_value(name: str, value: object, spec: dict[str, Any]) -> None:
    if "const" in spec:
        assert value == spec["const"], name
    if "enum" in spec:
        assert value in spec["enum"], (name, value)
    types = spec.get("type")
    allowed = types if isinstance(types, list) else [types] if types else []
    if value is None:
        assert "null" in allowed or None in spec.get("enum", []), name
        return
    if "integer" in allowed:
        assert type(value) is int, name
        assert value >= spec.get("minimum", value), name
    if "string" in allowed or spec.get("format") or spec.get("pattern"):
        assert isinstance(value, str), name
        if spec.get("format") == "uuid":
            assert _UUID.fullmatch(value), name
        if spec.get("format") == "date":
            date.fromisoformat(value)
        if spec.get("format") == "date-time":
            assert value.endswith("Z"), name
            datetime.fromisoformat(value)
        if spec.get("pattern"):
            assert re.search(spec["pattern"], value), name
    if "object" in allowed and isinstance(value, dict):
        props = spec.get("properties", {})
        assert set(value) <= set(props), name
        assert set(spec.get("required", [])) <= set(value), name
        for key, item in value.items():
            _check_value(f"{name}.{key}", item, props[key])


def assert_payload_conforms(event_type: str, payload: dict[str, Any]) -> None:
    """Champs connus seulement, champs requis présents, types/enum/format respectés."""
    schema = _payload_schema(event_type)
    props = schema["properties"]
    assert set(payload) <= set(props), sorted(set(payload) - set(props))
    assert set(schema["required"]) <= set(payload), sorted(set(schema["required"]) - set(payload))
    for key, value in payload.items():
        _check_value(key, value, props[key])
