"""R10 et contrôle par attribut : une clinique ne voit que ses dossiers, une organisation que
les siens (sous ``mulema_app``, RLS forcée)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from api.claims.tests.conftest import ClaimsSeed
from api.claims.tests.flows import ITEMS_48000, ITEMS_185000, decide, new_claim


def _ids(client: TestClient, seed: ClaimsSeed, who: str) -> set[str]:
    response = client.get("/v1/claims?limit=200", headers=seed.auth(who))
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["items"]}


def test_une_clinique_ne_voit_que_ses_dossiers(client: TestClient, seed: ClaimsSeed) -> None:
    _, p1 = new_claim(client, seed, ITEMS_48000, who="clinique_p1")
    _, p2 = new_claim(client, seed, ITEMS_48000, who="clinique_p2")
    p1_id, p2_id = p1["claim"]["id"], p2["claim"]["id"]

    seen_by_p1 = _ids(client, seed, "clinique_p1")
    assert p1_id in seen_by_p1
    assert p2_id not in seen_by_p1
    other = client.get(f"/v1/claims/{p2_id}", headers=seed.auth("clinique_p1"))
    assert other.status_code == 404
    assert other.json()["code"] == "NOT-01"

    assert {p1_id, p2_id} <= _ids(client, seed, "gestionnaire")
    assert {p1_id, p2_id} <= _ids(client, seed, "medecin_conseil")


def test_aucune_fuite_entre_organisations(client: TestClient, seed: ClaimsSeed) -> None:
    _, a = new_claim(client, seed, ITEMS_185000)
    a_id = a["claim"]["id"]
    b_id = str(seed.scalar("SELECT id FROM claims WHERE organization_id = %s", (seed.orgs["b"],)))

    for who in ("gestionnaire_b", "medecin_conseil_b", "clinique_b"):
        assert a_id not in _ids(client, seed, who)
        assert client.get(f"/v1/claims/{a_id}", headers=seed.auth(who)).status_code == 404
    assert decide(client, seed, a_id, "accorder", who="medecin_conseil_b").status_code == 404
    assert b_id in _ids(client, seed, "gestionnaire_b")
    for who in ("gestionnaire", "clinique_p1"):
        assert b_id not in _ids(client, seed, who)
        assert client.get(f"/v1/claims/{b_id}", headers=seed.auth(who)).status_code == 404


def test_dossier_inconnu(client: TestClient, seed: ClaimsSeed) -> None:
    response = client.get(f"/v1/claims/{uuid.uuid4()}", headers=seed.auth("gestionnaire"))
    assert response.status_code == 404


def test_filtres_et_pagination(client: TestClient, seed: ClaimsSeed) -> None:
    member, body = new_claim(client, seed, ITEMS_185000)
    listed = client.get(
        f"/v1/claims?status=en_revue&member_id={member.member_id}",
        headers=seed.auth("gestionnaire"),
    ).json()
    assert [item["id"] for item in listed["items"]] == [body["claim"]["id"]]
    assert listed["items"][0]["provider_name"] == "Clinique fictive P1"

    page = client.get("/v1/claims?limit=1", headers=seed.auth("gestionnaire")).json()
    assert len(page["items"]) == 1
    assert page["page"]["next_cursor"]
    following = client.get(
        f"/v1/claims?limit=1&cursor={page['page']['next_cursor']}",
        headers=seed.auth("gestionnaire"),
    ).json()
    assert following["items"][0]["id"] != page["items"][0]["id"]


def test_file_de_travail_calculee(client: TestClient, seed: ClaimsSeed) -> None:
    before = client.get("/v1/work-queue", headers=seed.auth("gestionnaire")).json()
    new_claim(client, seed, ITEMS_185000)
    new_claim(client, seed, ITEMS_48000)
    after = client.get("/v1/work-queue", headers=seed.auth("gestionnaire")).json()
    assert after["claims_in_review"] == before["claims_in_review"] + 1
    assert after["auto_approved_today"] == before["auto_approved_today"] + 1
    assert client.get("/v1/work-queue", headers=seed.auth("clinique_p1")).status_code == 403
