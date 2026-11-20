"""R11 — « Chaque réponse cite ses sources » et « chaque action est journalisée avec ses sources ».

Sans source, JOE refuse (``kind: refus``). Le motif médical n'est jamais lu : une question qui
le demande est refusée sans appel à HealthOS.
"""

from __future__ import annotations

from typing import Any

import pytest

from api.joe.tests.support import JoeHarness, ai_actions


def _ask(h: JoeHarness, who: str, body: dict[str, Any]) -> dict[str, Any]:
    response = h.client.post("/v1/joe/questions", json=body, headers=h.seed.auth(who))
    assert response.status_code == 200, response.text
    answer: dict[str, Any] = response.json()
    return answer


def _ids(sources: list[dict[str, Any]], kind: str) -> set[str]:
    return {s["id"] for s in sources if s["type"] == kind}


def test_une_reponse_sur_un_dossier_cite_le_dossier_et_l_adherent(harness: JoeHarness) -> None:
    s = harness.scenario
    answer = _ask(harness, "gestionnaire", {"question": "Où en est ce dossier ?",
                                            "claim_id": s.review_claim_id})  # fmt: skip
    assert answer["kind"] == "reponse"
    assert s.review_claim_id in _ids(answer["sources"], "claim")
    assert str(s.member.member_id) in _ids(answer["sources"], "member")
    assert all(src.get("label") for src in answer["sources"])
    assert s.review_claim_number in answer["answer"]


def test_le_journal_garde_chaque_lecture_et_la_reponse_avec_leurs_sources(
    harness: JoeHarness,
) -> None:
    s, seed = harness.scenario, harness.seed
    user = seed.users["gestionnaire"]
    already = {a["id"] for a in ai_actions(seed, user)}
    answer = _ask(harness, "gestionnaire", {"question": "Droits et historique de l'adhérent ?",
                                            "member_id": str(s.member.member_id)})  # fmt: skip
    new = [a for a in ai_actions(seed, user) if a["id"] not in already]

    final = [a for a in new if a["id"] == answer["ai_action_id"]]
    assert len(final) == 1
    assert final[0]["kind"] == "reponse"
    assert final[0]["tool"] == "repondre_question"
    assert final[0]["model"] == "espion-deterministe"
    stored = {(x["type"], x["id"]) for x in final[0]["sources"]}
    assert stored == {(x["type"], x["id"]) for x in answer["sources"]}

    lectures = {a["tool"]: a for a in new if a["kind"] == "lecture"}
    assert {"lire_droits", "lire_historique"} <= set(lectures)
    for lecture in lectures.values():
        assert lecture["sources"], lecture["tool"]
        assert {(x["type"], x["id"]) for x in lecture["sources"]} <= stored
    assert s.auto_claim_id in _ids(answer["sources"], "claim")
    assert s.review_claim_id in _ids(answer["sources"], "claim")


def test_le_bareme_cite_les_lignes_de_tarif(harness: JoeHarness) -> None:
    answer = _ask(
        harness, "medecin_conseil", {"question": "Quel est le tarif d'une consultation ?"}
    )
    assert answer["kind"] == "reponse"
    assert _ids(answer["sources"], "tariff_item")
    assert "CONS-GEN" in answer["answer"]


def test_sans_source_joe_refuse(harness: JoeHarness) -> None:
    seed = harness.seed
    answer = _ask(harness, "admin", {"question": "Quelle est la météo demain ?"})
    assert answer["kind"] == "refus"
    assert answer["sources"] == []
    rows = [a for a in ai_actions(seed, seed.users["admin"]) if a["id"] == answer["ai_action_id"]]
    assert rows[0]["kind"] == "refus"
    assert rows[0]["sources"] == []


@pytest.mark.parametrize(
    "question",
    [
        "Quel est le motif de la consultation ?",
        "Quel diagnostic pour ce dossier ?",
        "Montre-moi l'ordonnance",
        "Quelle maladie a ce patient ?",
    ],
)
def test_le_motif_medical_n_est_jamais_lu(harness: JoeHarness, question: str) -> None:
    seed, s = harness.seed, harness.scenario
    calls_before = len(seed.healthos.requests)
    audits_before = seed.scalar(
        "SELECT count(*) FROM audit_events WHERE action = 'claim.medical_reason.read'"
    )

    answer = _ask(harness, "medecin_conseil", {"question": question,
                                               "claim_id": s.review_claim_id})  # fmt: skip

    assert answer["kind"] == "refus"
    assert answer["sources"] == []
    assert "médecin-conseil" in answer["answer"]
    assert len(seed.healthos.requests) == calls_before
    assert (
        seed.scalar("SELECT count(*) FROM audit_events WHERE action = 'claim.medical_reason.read'")
        == audits_before
    )


def test_le_brouillon_de_decision_cite_ses_sources(harness: JoeHarness) -> None:
    s, seed = harness.scenario, harness.seed
    response = harness.client.post(
        "/v1/joe/decision-drafts",
        json={"claim_id": s.review_claim_id},
        headers=seed.auth("medecin_conseil"),
    )
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["claim_id"] == s.review_claim_id
    assert s.review_claim_id in _ids(draft["sources"], "claim")
    assert str(s.member.member_id) in _ids(draft["sources"], "member")
    assert draft["rationale"]
    # Aucune pièce déposée sur ce dossier : JOE propose de les demander (Q-L8-02).
    assert draft["recommendation"] == "demander_pieces"


def test_brouillon_de_decision_d_un_dossier_hors_revue_introuvable(harness: JoeHarness) -> None:
    response = harness.client.post(
        "/v1/joe/decision-drafts",
        json={"claim_id": harness.scenario.auto_claim_id},
        headers=harness.seed.auth("medecin_conseil"),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT-01"


@pytest.mark.parametrize(
    ("purpose", "kind"),
    [("relance_cotisation", "contribution"), ("confirmation_accord", "claim")],
)
def test_le_brouillon_de_message_cite_ses_sources(
    harness: JoeHarness, purpose: str, kind: str
) -> None:
    s, seed = harness.scenario, harness.seed
    response = harness.client.post(
        "/v1/joe/message-drafts",
        json={"member_id": str(s.member.member_id), "purpose": purpose},
        headers=seed.auth("gestionnaire"),
    )
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["channel"] == "sms"
    assert draft["text"]
    assert str(s.member.member_id) in _ids(draft["sources"], "member")
    assert _ids(draft["sources"], kind)
    for needle in ("Aminata", "Kouassi", s.member.phone or "", "CONS-", "IMG-"):
        assert needle not in draft["text"]


def test_journal_reserve_a_l_admin_et_sources_presentes(harness: JoeHarness) -> None:
    seed = harness.seed
    _ask(harness, "gestionnaire", {"question": "Barème des actes ?"})
    denied = harness.client.get("/v1/ai-actions", headers=seed.auth("gestionnaire"))
    assert denied.status_code == 403

    response = harness.client.get("/v1/ai-actions?limit=200", headers=seed.auth("admin"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"]
    assert "next_cursor" in body["page"]
    for item in body["items"]:
        assert set(item) >= {"id", "occurred_at", "user_id", "kind", "tool", "sources"}
        if item["kind"] in {"reponse", "preparation"}:
            assert item["sources"], item


def test_journal_pagine(harness: JoeHarness) -> None:
    seed, client = harness.seed, harness.client
    for _ in range(3):
        _ask(harness, "gestionnaire", {"question": "Barème des actes ?"})
    first = client.get("/v1/ai-actions?limit=2", headers=seed.auth("admin")).json()
    assert len(first["items"]) == 2
    cursor = first["page"]["next_cursor"]
    assert cursor
    second = client.get(f"/v1/ai-actions?limit=2&cursor={cursor}", headers=seed.auth("admin"))
    assert second.status_code == 200
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second.json()["items"]}
    bad = client.get("/v1/ai-actions?cursor=zz", headers=seed.auth("admin"))
    assert bad.status_code == 422


def test_isolation_un_utilisateur_de_b_n_obtient_rien_de_a(harness: JoeHarness) -> None:
    s, seed, client = harness.scenario, harness.seed, harness.client
    answer = _ask(harness, "gestionnaire_b", {"question": "Résume ce dossier",
                                              "claim_id": s.review_claim_id})  # fmt: skip
    assert answer["kind"] == "refus"
    assert answer["sources"] == []
    assert s.review_claim_number not in answer["answer"]

    draft = client.post(
        "/v1/joe/decision-drafts",
        json={"claim_id": s.review_claim_id},
        headers=seed.auth("medecin_conseil_b"),
    )
    assert draft.status_code == 404
    message = client.post(
        "/v1/joe/message-drafts",
        json={"member_id": str(s.member.member_id), "purpose": "relance_cotisation"},
        headers=seed.auth("gestionnaire_b"),
    )
    assert message.status_code == 404
