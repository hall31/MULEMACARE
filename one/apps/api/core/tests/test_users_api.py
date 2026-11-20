"""Utilisateurs et rôles (createUser, listUsers, replaceUserRoles), audités."""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from api.core.tests.conftest import CoreSeed, owner_count


def _subject() -> str:
    return f"idp-fictif-{uuid.uuid4().hex}"


def _audit_count(seed: CoreSeed, action: str, target: str) -> int:
    return owner_count(
        seed,
        "SELECT count(*) FROM audit_events WHERE action = %s AND target_id = %s",
        (action, target),
    )


def test_creer_un_utilisateur(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.post(
        "/v1/users",
        json={
            "idp_subject": _subject(),
            "display_name": "Agent fictif créé",
            "email": "agent.fictif@example.invalid",
            "roles": [{"role": "clinique", "provider_id": str(core_seed.providers["a"])}],
        },
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "active"
    assert body["roles"] == [
        {
            "role": "clinique",
            "provider_id": str(core_seed.providers["a"]),
            "employer_id": None,
            "member_id": None,
        }
    ]
    assert "idp_subject" not in body
    assert (
        owner_count(
            core_seed,
            "SELECT count(*) FROM users WHERE id = %s AND organization_id = %s",
            (body["id"], core_seed.orgs["a"]),
        )
        == 1
    )
    assert _audit_count(core_seed, "user.created", body["id"]) == 1


def test_le_nouvel_utilisateur_est_dans_l_organisation_du_jeton(
    client: TestClient, core_seed: CoreSeed
) -> None:
    """Un champ organization_id glissé dans le corps est refusé (additionalProperties: false)."""
    response = client.post(
        "/v1/users",
        json={
            "idp_subject": _subject(),
            "display_name": "Intrus",
            "roles": [{"role": "gestionnaire"}],
            "organization_id": str(core_seed.orgs["b"]),
        },
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"


def test_sujet_deja_rattache_409(client: TestClient, core_seed: CoreSeed) -> None:
    subject = _subject()
    payload = {"idp_subject": subject, "display_name": "Agent", "roles": [{"role": "gestionnaire"}]}
    first = client.post("/v1/users", json=payload, headers=core_seed.auth("a", "admin"))
    assert first.status_code == 201
    second = client.post("/v1/users", json=payload, headers=core_seed.auth("a", "admin"))
    assert second.status_code == 409
    assert second.json()["code"] == "VAL-01"
    # Même sujet dans l'autre organisation : autorisé (unicité par organisation).
    other = client.post("/v1/users", json=payload, headers=core_seed.auth("b", "admin"))
    assert other.status_code == 201


def test_role_clinique_sans_etablissement_422(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.post(
        "/v1/users",
        json={"idp_subject": _subject(), "display_name": "A", "roles": [{"role": "clinique"}]},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VAL-01"
    assert body["errors"]


def test_etablissement_d_une_autre_organisation_refuse(
    client: TestClient, core_seed: CoreSeed
) -> None:
    response = client.post(
        "/v1/users",
        json={
            "idp_subject": _subject(),
            "display_name": "A",
            "roles": [{"role": "clinique", "provider_id": str(core_seed.providers["b"])}],
        },
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"
    assert response.json()["errors"][0]["field"] == "roles.0.provider_id"


def _member_of(seed: CoreSeed, org: str) -> str:
    with psycopg.connect(seed.dsn) as conn:
        row = conn.execute(
            "SELECT id FROM members WHERE organization_id = %s LIMIT 1", (seed.orgs[org],)
        ).fetchone()
    assert row is not None
    return str(row[0])


def test_compte_adherent_rattache_a_un_contrat_de_l_organisation(
    client: TestClient, core_seed: CoreSeed
) -> None:
    """Phase 1 (CR-P1-01) : le rôle adhérent porte le contrat qu'il peut consulter."""
    member = _member_of(core_seed, "a")
    response = client.post(
        "/v1/users",
        json={
            "idp_subject": _subject(),
            "display_name": "Adhérent fictif",
            "roles": [{"role": "adherent", "member_id": member}],
        },
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 201, response.text
    assert response.json()["roles"] == [
        {"role": "adherent", "provider_id": None, "employer_id": None, "member_id": member}
    ]
    assert _audit_count(core_seed, "user.created", response.json()["id"]) == 1


def test_compte_adherent_sans_contrat_422(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.post(
        "/v1/users",
        json={"idp_subject": _subject(), "display_name": "A", "roles": [{"role": "adherent"}]},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"


def test_contrat_d_une_autre_organisation_refuse(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.post(
        "/v1/users",
        json={
            "idp_subject": _subject(),
            "display_name": "A",
            "roles": [{"role": "adherent", "member_id": _member_of(core_seed, "b")}],
        },
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"
    assert response.json()["errors"][0]["field"] == "roles.0.member_id"


def test_member_id_interdit_hors_role_adherent(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.post(
        "/v1/users",
        json={
            "idp_subject": _subject(),
            "display_name": "A",
            "roles": [{"role": "gestionnaire", "member_id": _member_of(core_seed, "a")}],
        },
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 422


def test_au_moins_un_role_a_la_creation(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.post(
        "/v1/users",
        json={"idp_subject": _subject(), "display_name": "A", "roles": []},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 422


def test_seul_l_admin_cree_des_utilisateurs(client: TestClient, core_seed: CoreSeed) -> None:
    for role in ("gestionnaire", "medecin_conseil", "clinique", "employeur"):
        response = client.post(
            "/v1/users",
            json={"idp_subject": _subject(), "display_name": "A", "roles": [{"role": "admin"}]},
            headers=core_seed.auth("a", role),
        )
        assert response.status_code == 403, role
        assert response.json()["code"] == "AUTH-02"


def test_ajouter_un_role_est_audite(client: TestClient, core_seed: CoreSeed) -> None:
    user = core_seed.add_user("a", f"ajout-{uuid.uuid4().hex[:6]}", [("gestionnaire", None, None)])
    response = client.put(
        f"/v1/users/{user}/roles",
        json={"roles": [{"role": "gestionnaire"}, {"role": "medecin_conseil"}]},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 200, response.text
    assert sorted(g["role"] for g in response.json()["roles"]) == [
        "gestionnaire",
        "medecin_conseil",
    ]
    assert _audit_count(core_seed, "user.roles_replaced", str(user)) == 1
    with psycopg.connect(core_seed.dsn) as conn:
        row = conn.execute(
            "SELECT granted_by FROM user_roles WHERE user_id = %s AND role = 'medecin_conseil'",
            (user,),
        ).fetchone()
    assert row == (core_seed.users[("a", "admin")],)


def test_meme_ensemble_de_roles_sans_changement(client: TestClient, core_seed: CoreSeed) -> None:
    user = core_seed.add_user("a", f"idem-{uuid.uuid4().hex[:6]}", [("gestionnaire", None, None)])
    response = client.put(
        f"/v1/users/{user}/roles",
        json={"roles": [{"role": "gestionnaire"}, {"role": "gestionnaire"}]},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 200
    assert [g["role"] for g in response.json()["roles"]] == ["gestionnaire"]


def test_retrait_de_role_refuse_tant_que_le_contrat_ne_le_permet_pas(
    client: TestClient, core_seed: CoreSeed
) -> None:
    """Le rôle applicatif n'a pas DELETE sur user_roles (contrat L0) : CR-L1-02 ouverte.

    Le retrait est refusé explicitement (409, rien de modifié) au lieu d'échouer en 500.
    """
    user = core_seed.add_user(
        "a",
        f"retrait-{uuid.uuid4().hex[:6]}",
        [("gestionnaire", None, None), ("medecin_conseil", None, None)],
    )
    response = client.put(
        f"/v1/users/{user}/roles",
        json={"roles": [{"role": "gestionnaire"}]},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "VAL-01"
    assert (
        owner_count(core_seed, "SELECT count(*) FROM user_roles WHERE user_id = %s", (user,)) == 2
    )
    assert _audit_count(core_seed, "user.roles_replaced", str(user)) == 0


def test_roles_d_un_utilisateur_inconnu_404(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.put(
        f"/v1/users/{uuid.uuid4()}/roles",
        json={"roles": [{"role": "gestionnaire"}]},
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT-01"


def test_pagination_des_utilisateurs(client: TestClient, core_seed: CoreSeed) -> None:
    first = client.get("/v1/users", params={"limit": 2}, headers=core_seed.auth("a", "admin"))
    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    cursor = first.json()["page"]["next_cursor"]
    assert cursor
    second = client.get(
        "/v1/users", params={"limit": 2, "cursor": cursor}, headers=core_seed.auth("a", "admin")
    )
    assert {u["id"] for u in first.json()["items"]}.isdisjoint(
        {u["id"] for u in second.json()["items"]}
    )


def test_curseur_invalide_422(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.get(
        "/v1/users", params={"cursor": "n'importe quoi"}, headers=core_seed.auth("a", "admin")
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"


def test_limite_hors_bornes_422(client: TestClient, core_seed: CoreSeed) -> None:
    response = client.get("/v1/users", params={"limit": 500}, headers=core_seed.auth("a", "admin"))
    assert response.status_code == 422
    assert response.json()["code"] == "VAL-01"
