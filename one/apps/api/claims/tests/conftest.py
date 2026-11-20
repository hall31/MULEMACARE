"""Fixtures du lot L5 : base `insurance` par module, API sous le rôle ``mulema_app``.

- Organisation A : jeu de démonstration (règles et seuils du PRD §5, produit FAMILLE-OR, barème),
  plus trois prestataires (P1 et P2 conventionnés, un hors réseau) et un utilisateur par rôle.
- Organisation B : jeu d'isolation du lot L0 (une ligne par table, dont un dossier).
- Adhérents, cartes et cotisations : insérés en SQL par le propriétaire (fixtures, pas le code
  de L4). Toutes les données sont fictives.
- HealthOS : serveur FHIR simulé (L9) ; SMS : fournisseur simulé ; QR : vérificateur de test.
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL

from api.claims.ports import ClaimsRuntime, SimulatedSmsSender
from api.claims.routes import install
from api.claims.tests.support import T0, FakeQrVerifier, MutableClock, ScriptedFraudScorer
from api.core.app import create_app
from api.core.identity import Identity, InMemoryIdentityProvider
from api.core.settings import Settings
from api.integrations.egress import EgressAllowlist, Endpoint
from api.integrations.healthos import HealthOSClient
from api.integrations.healthos_sim import SimulatedHealthOS
from api.integrations.transport import GuardedHttpTransport
from api.tests.contracts.helpers import apply_sql_file
from api.tests.paths import DEMO_SEED_SQL, SCHEMA_SQL

ORG_A = UUID("00000000-0000-4000-8000-000000000001")
PLAN_A = UUID("00000000-0000-4000-8000-000000000101")
APP_ROLE = "mulema_app"
ISOLATION_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "contracts"
    / "fixtures"
    / "one_row_per_table.sql"
)


def sqlalchemy_url(conninfo: str) -> str:
    params = {k: str(v) for k, v in conninfo_to_dict(conninfo).items() if v is not None}
    database = params.pop("dbname")
    user = params.pop("user", None)
    password = params.pop("password", None)
    url = URL.create(
        "postgresql+psycopg", username=user, password=password, database=database, query=params
    )
    return url.render_as_string(hide_password=False)


@dataclass(frozen=True)
class MemberRef:
    """Adhérent fictif : identifiants internes, carte et QR de test."""

    member_id: UUID
    person_id: UUID
    card_id: UUID
    member_number: str
    qr_payload: str
    pseudonym: UUID
    phone: str | None
    dependent_person_id: UUID | None = None


@dataclass
class ClaimsSeed:
    dsn: str
    url: str
    orgs: dict[str, UUID]
    providers: dict[str, UUID]
    users: dict[str, UUID]
    idp: InMemoryIdentityProvider
    qr: FakeQrVerifier
    sms: SimulatedSmsSender
    fraud: ScriptedFraudScorer
    clock: MutableClock
    healthos: SimulatedHealthOS
    tokens: dict[str, str] = field(default_factory=dict)
    _numbers: list[int] = field(default_factory=lambda: [1000])

    def auth(self, who: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[who]}"}

    def owner(self) -> psycopg.Connection[Any]:
        """Connexion propriétaire (superutilisateur : hors RLS) pour poser et vérifier."""
        return psycopg.connect(self.dsn)

    def scalar(self, query: str, params: tuple[object, ...] = ()) -> Any:  # noqa: ANN401
        with self.owner() as conn:
            row = conn.execute(query.encode(), params).fetchone()
        return None if row is None else row[0]

    def add_user(self, who: str, org: str, roles: list[tuple[str, UUID | None]]) -> UUID:
        org_id = self.orgs[org]
        subject = f"sub-{who}-{uuid.uuid4().hex[:8]}"
        with self.owner() as conn:
            row = conn.execute(
                "INSERT INTO users (organization_id, idp_subject, display_name) "
                "VALUES (%s, %s, %s) RETURNING id",
                (org_id, subject, f"Agent fictif {who}"),
            ).fetchone()
            assert row is not None
            user_id: UUID = row[0]
            for role, provider in roles:
                conn.execute(
                    "INSERT INTO user_roles (organization_id, user_id, role, provider_id) "
                    "VALUES (%s, %s, %s, %s)",
                    (org_id, user_id, role, provider),
                )
        self.users[who] = user_id
        self.tokens[who] = self.idp.issue(Identity(subject=subject, organization_id=org_id))
        return user_id

    def new_member(  # noqa: PLR0913 — fixture d'adhérent paramétrable
        self,
        *,
        status: str = "actif",
        enrolled_on: date = date(2026, 1, 1),
        no_phone: bool = False,
        with_dependent: bool = False,
        unpaid_since: date | None = None,
        card_status: str = "active",
    ) -> MemberRef:
        """Adhérent fictif de l'organisation A avec sa carte active (fixture SQL, pas L4)."""
        self._numbers[0] += 1
        number = f"MC-{self._numbers[0]:08d}"
        phone = None if no_phone else f"+22507{self._numbers[0]:08d}"
        qr_payload = f"QR-TEST-{secrets.token_hex(12)}"
        with self.owner() as conn:
            conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(ORG_A),))
            person = conn.execute(
                "INSERT INTO persons (organization_id, given_name, family_name, birth_date, "
                "phone_e164) VALUES (%s, 'Prénom', 'Fictif', DATE '1990-01-01', %s) "
                "RETURNING id, healthos_pseudonym",
                (ORG_A, phone),
            ).fetchone()
            assert person is not None
            member = conn.execute(
                "INSERT INTO members (organization_id, person_id, member_number, plan_id, status, "
                "enrolled_on, waiting_period_ends_on) VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id",
                (ORG_A, person[0], number, PLAN_A, status, enrolled_on, enrolled_on),
            ).fetchone()
            assert member is not None
            dependent: UUID | None = None
            if with_dependent:
                dep = conn.execute(
                    "INSERT INTO persons (organization_id, given_name, family_name, birth_date) "
                    "VALUES (%s, 'Enfant', 'Fictif', DATE '2020-01-01') RETURNING id",
                    (ORG_A,),
                ).fetchone()
                assert dep is not None
                dependent = dep[0]
                conn.execute(
                    "INSERT INTO dependents (organization_id, member_id, person_id, relationship, "
                    "valid_from) VALUES (%s, %s, %s, 'enfant', %s)",
                    (ORG_A, member[0], dependent, enrolled_on),
                )
            card = conn.execute(
                "INSERT INTO cards (organization_id, member_id, person_id, qr_secret_ciphertext, "
                "status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (ORG_A, member[0], person[0], secrets.token_bytes(16), card_status),
            ).fetchone()
            assert card is not None
            if unpaid_since is not None:
                conn.execute(
                    "INSERT INTO contributions (organization_id, member_id, period_start, due_on, "
                    "amount_xof, status) VALUES (%s, %s, %s, %s, 27500, 'en_retard')",
                    (ORG_A, member[0], unpaid_since.replace(day=1), unpaid_since),
                )
        self.qr.cards[qr_payload] = card[0]
        return MemberRef(
            member_id=member[0],
            person_id=person[0],
            card_id=card[0],
            member_number=number,
            qr_payload=qr_payload,
            pseudonym=person[1],
            phone=phone,
            dependent_person_id=dependent,
        )


def _provider(conn: psycopg.Connection[Any], name: str, *, convention: bool) -> UUID:
    row = conn.execute(
        "INSERT INTO providers (organization_id, name, kind, city, country_code) "
        "VALUES (%s, %s, 'clinique', 'Abidjan', 'CI') RETURNING id",
        (ORG_A, name),
    ).fetchone()
    assert row is not None
    if convention:
        conn.execute(
            "INSERT INTO provider_conventions (organization_id, provider_id, valid_from) "
            "VALUES (%s, %s, DATE '2026-01-01')",
            (ORG_A, row[0]),
        )
    provider: UUID = row[0]
    return provider


@pytest.fixture(scope="module")
def claims_seed(pg_server_dsn: str) -> Iterator[ClaimsSeed]:
    name = f"claims_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    dsn = make_conninfo(pg_server_dsn, dbname=name)
    try:
        apply_sql_file(dsn, SCHEMA_SQL)
        apply_sql_file(dsn, DEMO_SEED_SQL)
        org_b = uuid.uuid4()
        script = ISOLATION_FIXTURE.read_text(encoding="utf-8")
        with psycopg.connect(dsn) as conn:
            conn.execute(
                script.replace("__ORG__", str(org_b)).replace("__SLUG__", "org-b").encode()
            )
            conn.execute("SELECT set_config('app.organization_id', %s, true)", (str(ORG_A),))
            providers = {
                "p1": _provider(conn, "Clinique fictive P1", convention=True),
                "p2": _provider(conn, "Clinique fictive P2", convention=True),
                "hors_reseau": _provider(conn, "Clinique fictive hors réseau", convention=False),
            }
            row = conn.execute(
                "SELECT id FROM providers WHERE organization_id = %s", (org_b,)
            ).fetchone()
            assert row is not None
            providers["b"] = row[0]
        with SimulatedHealthOS() as healthos:
            seed = ClaimsSeed(
                dsn=dsn,
                url=sqlalchemy_url(dsn),
                orgs={"a": ORG_A, "b": org_b},
                providers=providers,
                users={},
                idp=InMemoryIdentityProvider(),
                qr=FakeQrVerifier(),
                sms=SimulatedSmsSender(),
                fraud=ScriptedFraudScorer(value=Decimal("0.06")),
                clock=MutableClock(),
                healthos=healthos,
            )
            seed.add_user("clinique_p1", "a", [("clinique", providers["p1"])])
            seed.add_user("clinique_p2", "a", [("clinique", providers["p2"])])
            seed.add_user("clinique_hors_reseau", "a", [("clinique", providers["hors_reseau"])])
            for role in ("gestionnaire", "medecin_conseil", "admin", "employeur_sans_droit"):
                seed.add_user(role, "a", [] if role == "employeur_sans_droit" else [(role, None)])
            seed.add_user("clinique_b", "b", [("clinique", providers["b"])])
            seed.add_user("gestionnaire_b", "b", [("gestionnaire", None)])
            seed.add_user("medecin_conseil_b", "b", [("medecin_conseil", None)])
            yield seed
    finally:
        with psycopg.connect(pg_server_dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture(scope="module")
def client(claims_seed: ClaimsSeed) -> Iterator[TestClient]:
    allowlist = EgressAllowlist(frozenset({Endpoint("127.0.0.1", claims_seed.healthos.port)}))
    runtime = ClaimsRuntime(
        healthos=HealthOSClient(
            base_url=claims_seed.healthos.fhir_base_url,
            transport=GuardedHttpTransport(allowlist, timeout_seconds=2),
        ),
        qr_verifier=claims_seed.qr,
        sms_sender=claims_seed.sms,
        fraud_scorer=claims_seed.fraud,
        clock=claims_seed.clock,
    )
    app = create_app(
        Settings(database_url=claims_seed.url, app_role=APP_ROLE, egress_allowlist=allowlist),
        identity_provider=claims_seed.idp,
    )
    install(app, runtime)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seed(claims_seed: ClaimsSeed) -> Iterator[ClaimsSeed]:
    """Le jeu du module, horloge remise à T0 et score de fraude par défaut (0,06)."""
    claims_seed.clock.current = T0
    claims_seed.fraud.value = Decimal("0.06")
    claims_seed.healthos.fail_with = None
    yield claims_seed
    claims_seed.clock.current = T0
