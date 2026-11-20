"""R10 — isolation par organisation, prouvée via l'API du noyau pour CHAQUE table métier.

La requête passe par le jeton, la dépendance FastAPI du noyau (``SET LOCAL ROLE mulema_app`` et
``app.organization_id``) puis la RLS forcée du contrat. Un utilisateur de A ne lit rien de B.
"""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from api.core.identity import Identity
from api.core.tests.conftest import CoreSeed, owner_count
from api.core.tests.probe import TABLES


def test_la_liste_des_tables_vient_du_contrat() -> None:
    assert len(TABLES) >= 30
    assert {"claims", "audit_events", "users", "user_roles", "ledger_lines"} <= set(TABLES)


@pytest.mark.parametrize("table", TABLES)
def test_un_utilisateur_de_a_ne_lit_rien_de_b(
    client: TestClient, core_seed: CoreSeed, table: str
) -> None:
    column = "id" if table == "organizations" else "organization_id"
    a, b = core_seed.orgs["a"], core_seed.orgs["b"]
    own = owner_count(core_seed, f"SELECT count(*) FROM {table} WHERE {column} = %s", (a,))
    assert own >= 1, f"{table} : le jeu ne contient aucune ligne pour A"

    response = client.get(
        f"/_probe/tables/{table}", params={"other": str(b)}, headers=core_seed.auth("a", "admin")
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["setting"] == str(a), "l'organisation injectée n'est pas celle du jeton"
    assert body["visible_for_other"] == 0, f"{table} : lignes de B visibles depuis A"
    # Les lignes créées en cours de module (utilisateurs, audit) sont celles de A.
    assert body["visible_total"] == owner_count(
        core_seed, f"SELECT count(*) FROM {table} WHERE {column} = %s", (a,)
    ), f"{table} : A ne voit pas exactement ses propres lignes"


@pytest.mark.parametrize("role", ["gestionnaire", "medecin_conseil", "clinique", "employeur"])
def test_isolation_ne_depend_pas_du_role(
    client: TestClient, core_seed: CoreSeed, role: str
) -> None:
    response = client.get(
        "/_probe/tables/claims",
        params={"other": str(core_seed.orgs["a"])},
        headers=core_seed.auth("b", role),
    )
    assert response.status_code == 200
    assert response.json()["visible_for_other"] == 0


def test_organisation_courante_est_celle_du_jeton(client: TestClient, core_seed: CoreSeed) -> None:
    for org in ("a", "b"):
        response = client.get("/v1/organization", headers=core_seed.auth(org, "gestionnaire"))
        assert response.status_code == 200
        assert response.json()["id"] == str(core_seed.orgs[org])
        assert response.json()["slug"] == f"org-{org}"


def test_liste_des_utilisateurs_sans_ceux_de_b(client: TestClient, core_seed: CoreSeed) -> None:
    ids: set[str] = set()
    cursor: str | None = None
    while True:
        params = {"limit": "3"} | ({"cursor": cursor} if cursor else {})
        response = client.get("/v1/users", params=params, headers=core_seed.auth("a", "admin"))
        assert response.status_code == 200, response.text
        ids |= {item["id"] for item in response.json()["items"]}
        cursor = response.json()["page"]["next_cursor"]
        if cursor is None:
            break
    b_users = {str(uid) for (org, _), uid in core_seed.users.items() if org == "b"}
    assert ids.isdisjoint(b_users)
    assert str(core_seed.users[("a", "gestionnaire")]) in ids


def test_modifier_les_roles_d_un_utilisateur_de_b_depuis_a_repond_404(
    client: TestClient, core_seed: CoreSeed
) -> None:
    target = core_seed.users[("b", "gestionnaire")]
    response = client.put(
        f"/v1/users/{target}/roles",
        json={"roles": [{"role": "gestionnaire"}, {"role": "admin"}]},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT-01"
    assert (
        owner_count(
            core_seed,
            "SELECT count(*) FROM user_roles WHERE user_id = %s AND role = 'admin'",
            (target,),
        )
        == 0
    )


def test_journal_d_audit_sans_evenement_de_b(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.get(
        "/v1/audit-events",
        params={"target_id": str(core_seed.claims["b"])},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_jeton_d_une_organisation_pour_un_sujet_d_une_autre_refuse(
    client: TestClient, core_seed: CoreSeed
) -> None:
    """Le sujet existe chez A ; un jeton qui prétend l'organisation B ne l'authentifie pas."""
    with psycopg.connect(core_seed.dsn) as conn:
        row = conn.execute(
            "SELECT idp_subject FROM users WHERE id = %s", (core_seed.users[("a", "admin")],)
        ).fetchone()
    assert row is not None
    token = core_seed.idp.issue(Identity(subject=row[0], organization_id=core_seed.orgs["b"]))
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH-01"
