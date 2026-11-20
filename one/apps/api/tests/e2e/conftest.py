"""Application ASSEMBLÉE (``create_app(..., modules=AppModules(...))``) sur une vraie base.

- Une seule application : noyau (L1), grand livre (L3), adhérents et cotisations (L4),
  comptoir et prises en charge (L5), sous le rôle ``mulema_app`` (RLS forcée).
- Dépendances réelles du code, fournisseurs externes simulés : HealthOS = serveur FHIR simulé
  (seule entrée de ``Settings.egress_allowlist``), SMS simulé, canal Wave simulé (secret
  aléatoire par module), identité de test (jetons opaques), QR dynamique RÉEL de L4
  (``CardQrVerifier``), score de fraude de test fixé à 0,06 (fournisseur non choisi, Q-L0-05).
- Organisation A : jeu de démonstration (règles et seuils du PRD §5). Organisation B : jeu
  d'isolation L0 (une ligne par table, dont un dossier). Prestataires et conventions posés en
  SQL par le propriétaire (les routes L2 sont prouvées dans apps/api/rules/tests).
- Marque blanche (CR-P3-02) : DNS de test en mémoire (``Platform.dns``, aucun appel réseau)
  et un hôte de logo dédié fictif (``LOGO_HOST``), distinct de la liste blanche d'egress.
- Toutes les données sont fictives.
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL

from api.branding.domains import StaticDnsTxt
from api.branding.service import BrandingPorts
from api.claims.ports import ClaimsRuntime, SimulatedSmsSender
from api.core.app import AppModules, create_app
from api.core.database import Database
from api.core.identity import Identity, InMemoryIdentityProvider
from api.core.settings import Settings
from api.integrations.egress import EgressAllowlist, Endpoint
from api.integrations.healthos import HealthOSClient
from api.integrations.healthos_sim import SimulatedHealthOS
from api.integrations.transport import GuardedHttpTransport
from api.joe.model import JoeModelSettings, build_language_model
from api.joe.ports import member_reader_factory
from api.joe.service import JoeRuntime
from api.members.cards import CardKeys, CardQrVerifier
from api.members.routes import MembersRuntime
from api.metrics.runtime import MetricsRuntime
from api.payments.channels import ChannelRegistry, SimulatedChannel
from api.payments.config import PaymentsConfig
from api.payments.routes import PaymentsRuntime
from api.rules.routes import RulesRuntime
from api.tests.contracts.helpers import APP_ROLE, apply_sql_file
from api.tests.paths import DEMO_SEED_SQL, SCHEMA_SQL, SPECS

ORG_A = UUID("00000000-0000-4000-8000-000000000001")
ORG_A_SLUG = "mulemacare-ci-demo"
START = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
PUBLIC_BASE_URL = "https://payer.mulemacare.invalid/p"
LOGO_HOST = "logos.assurance-fictive.ci"
TEST_FRAUD_SCORE = Decimal("0.06")
ISOLATION_FIXTURE = SPECS.parent / "apps" / "api" / "tests" / "contracts" / "fixtures"


def sqlalchemy_url(conninfo: str) -> str:
    params = {k: str(v) for k, v in conninfo_to_dict(conninfo).items() if v is not None}
    database = params.pop("dbname")
    user = params.pop("user", None)
    password = params.pop("password", None)
    url = URL.create(
        "postgresql+psycopg", username=user, password=password, database=database, query=params
    )
    return url.render_as_string(hide_password=False)


class TestClock:
    """Horloge UTC partagée par tous les modules de l'application assemblée."""

    __test__ = False

    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


@dataclass
class FixedFraudScorer:
    """Score de fraude de TEST (aucun fournisseur choisi, Q-L0-05)."""

    value: Decimal = TEST_FRAUD_SCORE

    async def score(self, *, member_id: UUID, provider_id: UUID) -> Decimal | None:
        del member_id, provider_id
        return self.value


@dataclass
class Platform:
    """Application assemblée démarrée, base et fournisseurs simulés."""

    dsn: str
    client: TestClient
    clock: TestClock
    idp: InMemoryIdentityProvider
    sms: SimulatedSmsSender
    wave: SimulatedChannel
    healthos: SimulatedHealthOS
    card_keys: CardKeys
    orgs: dict[str, UUID]
    providers: dict[str, UUID]
    dns: StaticDnsTxt = field(default_factory=StaticDnsTxt)
    users: dict[str, UUID] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)

    def auth(self, who: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[who]}"}

    def headers(self, who: str) -> dict[str, str]:
        return self.auth(who) | {"Idempotency-Key": f"cle-{uuid.uuid4().hex}"}

    @property
    def database(self) -> Database:
        database: Database = self.client.app.state.database  # type: ignore[attr-defined]
        return database

    def run[T](self, func: Callable[..., Awaitable[T]], *args: Any) -> T:  # noqa: ANN401
        """Coroutine exécutée dans la boucle de l'application (même pool, même rôle)."""
        portal = self.client.portal
        assert portal is not None
        return portal.call(func, *args)

    def rows(self, query: str, params: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
        """Lecture en propriétaire (hors RLS), pour les assertions seulement."""
        with psycopg.connect(self.dsn) as conn:
            return list(conn.execute(query.encode(), params).fetchall())

    def scalar(self, query: str, params: tuple[object, ...] = ()) -> Any:  # noqa: ANN401
        found = self.rows(query, params)
        assert len(found) == 1, found
        return found[0][0]

    def add_user(self, who: str, org: str, role: str, provider: UUID | None = None) -> None:
        subject = f"sub-e2e-{who}-{uuid.uuid4().hex[:8]}"
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "INSERT INTO users (organization_id, idp_subject, display_name) "
                "VALUES (%s, %s, %s) RETURNING id",
                (self.orgs[org], subject, f"Agent fictif {who}"),
            ).fetchone()
            assert row is not None
            conn.execute(
                "INSERT INTO user_roles (organization_id, user_id, role, provider_id) "
                "VALUES (%s, %s, %s, %s)",
                (self.orgs[org], row[0], role, provider),
            )
        self.users[who] = row[0]
        self.tokens[who] = self.idp.issue(Identity(subject=subject, organization_id=self.orgs[org]))


def _provider(conn: psycopg.Connection[Any], name: str) -> UUID:
    row = conn.execute(
        "INSERT INTO providers (organization_id, name, kind, city, country_code) "
        "VALUES (%s, %s, 'clinique', 'Abidjan', 'CI') RETURNING id",
        (ORG_A, name),
    ).fetchone()
    assert row is not None
    conn.execute(
        "INSERT INTO provider_conventions (organization_id, provider_id, valid_from) "
        "VALUES (%s, %s, DATE '2026-01-01')",
        (ORG_A, row[0]),
    )
    provider: UUID = row[0]
    return provider


def _seed(dsn: str) -> tuple[UUID, dict[str, UUID]]:
    apply_sql_file(dsn, SCHEMA_SQL)
    apply_sql_file(dsn, DEMO_SEED_SQL)
    org_b = uuid.uuid4()
    script = (ISOLATION_FIXTURE / "one_row_per_table.sql").read_text(encoding="utf-8")
    with psycopg.connect(dsn) as conn:
        conn.execute(script.replace("__ORG__", str(org_b)).replace("__SLUG__", "org-b").encode())
        conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(ORG_A),))
        providers = {"a": _provider(conn, "Clinique fictive A")}
        row = conn.execute(
            "SELECT id FROM providers WHERE organization_id = %s", (org_b,)
        ).fetchone()
        assert row is not None
        providers["b"] = row[0]
    return org_b, providers


@pytest.fixture(scope="module")
def platform(pg_server_dsn: str) -> Iterator[Platform]:
    name = f"e2e_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(pg_server_dsn, dbname=name)
    try:
        org_b, providers = _seed(dsn)
        with SimulatedHealthOS() as healthos:
            allowlist = EgressAllowlist(frozenset({Endpoint("127.0.0.1", healthos.port)}))
            clock = TestClock(START)
            idp = InMemoryIdentityProvider()
            sms = SimulatedSmsSender()
            card_keys = CardKeys(secrets.token_bytes(32))
            wave = SimulatedChannel("wave", secrets.token_bytes(32))
            dns = StaticDnsTxt()
            modules = AppModules(
                members=MembersRuntime(clock=clock, card_keys=card_keys),
                payments=PaymentsRuntime(
                    clock=clock,
                    config=PaymentsConfig(
                        link_secret=secrets.token_bytes(32),
                        public_base_url=PUBLIC_BASE_URL,
                        channels=ChannelRegistry([wave]),
                    ),
                ),
                claims=ClaimsRuntime(
                    healthos=HealthOSClient(
                        base_url=healthos.fhir_base_url,
                        transport=GuardedHttpTransport(allowlist, timeout_seconds=2),
                    ),
                    qr_verifier=CardQrVerifier(card_keys),
                    sms_sender=sms,
                    fraud_scorer=FixedFraudScorer(),
                    clock=clock,
                ),
                rules=RulesRuntime(clock=clock),
                joe=JoeRuntime(
                    clock=clock,
                    model=build_language_model(JoeModelSettings.from_env({})),
                    members=member_reader_factory(clock, card_keys),
                ),
                metrics=MetricsRuntime(clock=clock, pseudonym_key=secrets.token_bytes(32)),
                branding=BrandingPorts(
                    dns=dns,
                    logo_hosts=EgressAllowlist(frozenset({Endpoint(LOGO_HOST, 443)})),
                ),
            )
            app = create_app(
                Settings(
                    database_url=sqlalchemy_url(dsn), app_role=APP_ROLE, egress_allowlist=allowlist
                ),
                identity_provider=idp,
                modules=modules,
            )
            with TestClient(app) as client:
                env = Platform(
                    dsn=dsn,
                    client=client,
                    clock=clock,
                    idp=idp,
                    sms=sms,
                    wave=wave,
                    healthos=healthos,
                    card_keys=card_keys,
                    orgs={"a": ORG_A, "b": org_b},
                    providers=providers,
                    dns=dns,
                )
                env.add_user("gestionnaire", "a", "gestionnaire")
                env.add_user("medecin_conseil", "a", "medecin_conseil")
                env.add_user("clinique_a", "a", "clinique", providers["a"])
                env.add_user("clinique_b", "b", "clinique", providers["b"])
                yield env
    finally:
        with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )
