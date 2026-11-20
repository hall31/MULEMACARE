"""Authentification, injection de l'organisation (SET LOCAL) et erreurs typées à code stable."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.core.app import create_app
from api.core.database import Database, IsolationNotEnforcedError
from api.core.identity import Identity, InMemoryIdentityProvider
from api.core.settings import Settings
from api.core.tests.conftest import APP_ROLE, CoreSeed, owner_count
from api.core.tests.probe import probe_router

PROBLEM_KEYS = {"code", "message", "action", "request_id"}


def _assert_problem(response_json: dict[str, object], code: str) -> None:
    assert response_json.keys() >= PROBLEM_KEYS
    assert response_json["code"] == code
    for key in ("message", "action"):
        value = response_json[key]
        assert isinstance(value, str)
        assert value


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer jeton-inconnu"},
        {"Authorization": "Basic Zm9vOmJhcg=="},
        {"Authorization": "Bearer "},
    ],
)
def test_sans_jeton_valide_401_auth_01(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/v1/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    _assert_problem(response.json(), "AUTH-01")


def test_utilisateur_desactive_401(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.get("/v1/me", headers=core_seed.auth("a", "desactive"))
    assert response.status_code == 401
    _assert_problem(response.json(), "AUTH-01")


def test_sujet_inconnu_dans_l_organisation_401(client: TestClient, core_seed: CoreSeed) -> None:
    token = core_seed.idp.issue(
        Identity(subject="sub-jamais-cree", organization_id=core_seed.orgs["a"])
    )
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_role_insuffisant_403_auth_02(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.get("/v1/users", headers=core_seed.auth("a", "gestionnaire"))
    assert response.status_code == 403
    _assert_problem(response.json(), "AUTH-02")


def test_utilisateur_sans_role_403(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.get("/v1/me", headers=core_seed.auth("a", "sans_role"))
    assert response.status_code == 403
    _assert_problem(response.json(), "AUTH-02")


@pytest.mark.parametrize(
    "role", ["gestionnaire", "medecin_conseil", "clinique", "employeur", "admin"]
)
def test_me_renvoie_utilisateur_organisation_et_roles(
    client: TestClient, core_seed: CoreSeed, role: str
) -> None:
    response = client.get("/v1/me", headers=core_seed.auth("a", role))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["id"] == str(core_seed.users[("a", role)])
    assert body["organization"]["id"] == str(core_seed.orgs["a"])
    assert body["organization"]["currency"] == "XOF"
    assert [g["role"] for g in body["roles"]] == [role]
    assert body["roles"] == body["user"]["roles"]
    if role == "clinique":
        assert body["roles"][0]["provider_id"] == str(core_seed.providers["a"])
    if role == "employeur":
        assert body["roles"][0]["employer_id"] == str(core_seed.employers["a"])
    assert "idp_subject" not in response.text


def test_identifiant_de_requete_renvoye_et_repris(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.get(
        "/v1/users", headers=core_seed.auth("a", "gestionnaire") | {"X-Request-ID": "req-abc_123"}
    )
    assert response.headers["x-request-id"] == "req-abc_123"
    assert response.json()["request_id"] == "req-abc_123"


def test_identifiant_de_requete_non_conforme_remplace(client: TestClient) -> None:
    response = client.get("/v1/me", headers={"X-Request-ID": "Awa Fictive <script>"})
    assert response.headers["x-request-id"].startswith("req_")
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_route_inconnue_404_not_01(client: TestClient) -> None:
    response = client.get("/v1/nexiste-pas")
    assert response.status_code == 404
    _assert_problem(response.json(), "NOT-01")


def test_erreur_interne_500_sys_01_sans_detail(core_seed: CoreSeed) -> None:
    boom = APIRouter()

    @boom.get("/_boom")
    async def explode() -> None:
        raise RuntimeError("Awa Fictive +2250700000000")  # donnée à ne jamais renvoyer

    app = create_app(
        Settings(database_url=core_seed.url, app_role=APP_ROLE),
        identity_provider=InMemoryIdentityProvider(),
        routers=[boom],
    )
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/_boom")
    assert response.status_code == 500
    _assert_problem(response.json(), "SYS-01")
    assert "Awa" not in response.text


def test_echec_au_commit_jamais_de_faux_succes(core_seed: CoreSeed) -> None:
    """La transaction est validée AVANT l'envoi de la réponse (``scope="function"``).

    Une contrainte différée qui échoue au COMMIT doit produire une erreur, pas un 200 suivi
    d'une annulation silencieuse.
    """
    app = create_app(
        Settings(database_url=core_seed.url, app_role=APP_ROLE),
        identity_provider=core_seed.idp,
        routers=[probe_router],
    )
    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.post(
            "/_probe/deferred-commit-failure", headers=core_seed.auth("a", "gestionnaire")
        )
    assert response.status_code == 500
    _assert_problem(response.json(), "SYS-01")
    assert (
        owner_count(
            core_seed, "SELECT count(*) FROM ledger_entries WHERE entry_number LIKE 'SONDE-%%'", ()
        )
        == 0
    )


def test_set_local_ne_fuit_pas_d_une_transaction_a_l_autre(core_seed: CoreSeed) -> None:
    """``app.organization_id`` et le rôle sont locaux à la transaction (pool de connexions)."""

    async def scenario() -> tuple[str | None, str, str | None, str]:
        db = Database(core_seed.url, app_role=APP_ROLE, pool_size=1)
        try:
            async with db.transaction(core_seed.orgs["a"]) as session:
                inside: str | None = (
                    await session.execute(
                        text("SELECT current_setting('app.organization_id', true)")
                    )
                ).scalar_one()
                inside_role: str = (await session.execute(text("SELECT current_user"))).scalar_one()
            async with db.transaction(None) as session:
                after: str | None = (
                    await session.execute(
                        text("SELECT nullif(current_setting('app.organization_id', true), '')")
                    )
                ).scalar_one()
                after_role: str = (await session.execute(text("SELECT current_user"))).scalar_one()
            return inside, inside_role, after, after_role
        finally:
            await db.dispose()

    inside, inside_role, after, after_role = asyncio.run(scenario())
    assert inside == str(core_seed.orgs["a"])
    assert inside_role == APP_ROLE
    assert after is None
    assert after_role == APP_ROLE


def test_sans_organisation_la_base_ne_montre_rien(core_seed: CoreSeed) -> None:
    async def scenario() -> int:
        db = Database(core_seed.url, app_role=APP_ROLE)
        try:
            async with db.transaction(None) as session:
                return int((await session.execute(text("SELECT count(*) FROM users"))).scalar_one())
        finally:
            await db.dispose()

    assert asyncio.run(scenario()) == 0


def test_demarrage_refuse_si_la_rls_serait_contournee(core_seed: CoreSeed) -> None:
    """Connexion superutilisateur sans rôle applicatif : l'API refuse de démarrer."""

    async def scenario() -> None:
        db = Database(core_seed.url, app_role=None)
        try:
            await db.verify_isolation_enforced()
        finally:
            await db.dispose()

    with pytest.raises(IsolationNotEnforcedError):
        asyncio.run(scenario())


def test_nom_de_role_applicatif_valide() -> None:
    with pytest.raises(ValueError, match="rôle"):
        Database("postgresql+psycopg://x@/y", app_role='mulema_app"; DROP TABLE users; --')


def test_heure_de_session_en_utc(core_seed: CoreSeed) -> None:
    async def scenario() -> str:
        db = Database(core_seed.url, app_role=APP_ROLE)
        try:
            async with db.transaction(core_seed.orgs["a"]) as session:
                return str((await session.execute(text("SHOW TIME ZONE"))).scalar_one())
        finally:
            await db.dispose()

    assert asyncio.run(scenario()) == "UTC"


def test_organisation_du_jeton_est_un_uuid() -> None:
    with pytest.raises(TypeError):
        Identity(subject="s", organization_id="pas-un-uuid")  # type: ignore[arg-type]
    Identity(subject="s", organization_id=UUID(int=1))
