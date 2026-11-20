"""R5 — revue du médecin-conseil : décisions humaines et remise en revue par la clinique.

Seul le médecin-conseil décide d'un dossier en revue (Q-L0-12) ; la clinique remet le dossier
en revue en déposant les pièces demandées (``submitClaimDocuments``, Q-L0-20).
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from api.claims.tests.conftest import ClaimsSeed
from api.claims.tests.flows import (
    ITEMS_48000,
    ITEMS_185000,
    as_response,
    decide,
    drain_ledger,
    ledger_entries_for,
    new_claim,
    outbox,
)


def _submit(
    client: TestClient, seed: ClaimsSeed, claim_id: str, who: str = "clinique_p1"
) -> httpx.Response:
    return as_response(
        client.post(
            f"/v1/claims/{claim_id}/documents",
            json={"documents": [{"kind": "facture", "healthos_document_ref": "doc-fictif-42"}]},
            headers=seed.auth(who) | {"Idempotency-Key": f"cle-{uuid.uuid4().hex}"},
        )
    )


@pytest.mark.parametrize("who", ["gestionnaire", "admin", "clinique_p1"])
def test_seul_le_medecin_conseil_decide_d_un_dossier_en_revue(
    client: TestClient, seed: ClaimsSeed, who: str
) -> None:
    _, body = new_claim(client, seed, ITEMS_185000)
    claim_id = body["claim"]["id"]
    response = decide(client, seed, claim_id, "accorder", who=who)
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-02"
    assert seed.scalar("SELECT status FROM claims WHERE id = %s", (claim_id,)) == "en_revue"
    assert seed.scalar("SELECT count(*) FROM claim_decisions WHERE claim_id = %s", (claim_id,)) == 1


def test_le_medecin_conseil_accorde(client: TestClient, seed: ClaimsSeed) -> None:
    _, body = new_claim(client, seed, ITEMS_185000)
    claim_id = body["claim"]["id"]

    response = decide(client, seed, claim_id, "accorder")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["claim"]["status"] == "accordee"
    assert [d["outcome"] for d in detail["decisions"]] == ["en_revue", "accordee"]
    human = detail["decisions"][1]
    assert human["source"] == "humain"
    assert human["decided_by"] == str(seed.users["medecin_conseil"])
    assert human["reason_code"] == "MC-01"
    assert human["rule"] is None
    assert detail["decisions"][0]["rule"] == {"code": "R-20", "version": 2}

    decided = outbox(seed, claim_id)[-1][1]
    assert decided["outcome"] == "accordee"
    assert decided["source"] == "humain"
    assert decided["decided_by"] == str(seed.users["medecin_conseil"])
    assert decided["decision_sequence"] == 2

    drain_ledger(seed)
    assert ledger_entries_for(seed, claim_id) == 1


def test_le_medecin_conseil_refuse(client: TestClient, seed: ClaimsSeed) -> None:
    _, body = new_claim(client, seed, ITEMS_185000)
    claim_id = body["claim"]["id"]
    response = decide(client, seed, claim_id, "refuser", reason_code="ACT-02")
    assert response.json()["claim"]["status"] == "refusee"
    drain_ledger(seed)
    assert ledger_entries_for(seed, claim_id) == 0


def test_pieces_demandees_puis_remise_en_revue_par_la_clinique(
    client: TestClient, seed: ClaimsSeed
) -> None:
    _, body = new_claim(client, seed, ITEMS_185000)
    claim_id = body["claim"]["id"]
    asked = decide(client, seed, claim_id, "demander_pieces", reason_code="PCS-01")
    assert asked.json()["claim"]["status"] == "pieces_demandees"
    assert asked.json()["review_due_at"] is None

    # Tant que les pièces ne sont pas là, le médecin-conseil ne décide pas.
    assert decide(client, seed, claim_id, "accorder").status_code == 409

    other_clinic = _submit(client, seed, claim_id, who="clinique_p2")
    assert other_clinic.status_code == 404

    submitted = _submit(client, seed, claim_id)
    assert submitted.status_code == 200, submitted.text
    detail = submitted.json()
    assert detail["claim"]["status"] == "en_revue"
    assert detail["review_due_at"].startswith("2026-10-01T11:00:00")
    back = detail["decisions"][-1]
    assert (back["outcome"], back["source"], back["decided_by"]) == (
        "en_revue",
        "humain",
        str(seed.users["clinique_p1"]),
    )
    assert (
        seed.scalar(
            "SELECT healthos_document_ref FROM claim_documents WHERE claim_id = %s", (claim_id,)
        )
        == "doc-fictif-42"
    )
    assert [e[1]["outcome"] for e in outbox(seed, claim_id)[1:]] == [
        "en_revue",
        "pieces_demandees",
        "en_revue",
    ]

    assert decide(client, seed, claim_id, "accorder").status_code == 200


def test_pas_de_decision_hors_revue(client: TestClient, seed: ClaimsSeed) -> None:
    _, body = new_claim(client, seed, ITEMS_48000)
    response = decide(client, seed, body["claim"]["id"], "refuser")
    assert response.status_code == 409
    assert response.json()["code"] == "CLM-01"


def test_pas_de_pieces_sans_demande(client: TestClient, seed: ClaimsSeed) -> None:
    _, body = new_claim(client, seed, ITEMS_185000)
    response = _submit(client, seed, body["claim"]["id"])
    assert response.status_code == 409
    assert response.json()["code"] == "CLM-01"


def test_decision_idempotente(client: TestClient, seed: ClaimsSeed) -> None:
    _, body = new_claim(client, seed, ITEMS_185000)
    claim_id = body["claim"]["id"]
    first = decide(client, seed, claim_id, "accorder", key="cle-decision-0001")
    replay = decide(client, seed, claim_id, "accorder", key="cle-decision-0001")
    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert seed.scalar("SELECT count(*) FROM claim_decisions WHERE claim_id = %s", (claim_id,)) == 2


def test_motif_de_decision_code_seulement(client: TestClient, seed: ClaimsSeed) -> None:
    _, body = new_claim(client, seed, ITEMS_185000)
    response = decide(client, seed, body["claim"]["id"], "refuser", reason_code="texte libre")
    assert response.status_code == 422
