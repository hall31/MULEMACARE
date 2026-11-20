"""R11 — « Sans validation humaine, aucun état ne change » : instantané de TOUTES les tables
avant/après chaque opération de JOE. Seul ``ai_actions`` (journal en ajout seul) grandit.
"""

from __future__ import annotations

from typing import Any

import pytest

from api.joe.tests.support import JoeHarness, snapshot

JOURNAL = frozenset({"ai_actions"})


def _calls(h: JoeHarness) -> list[tuple[str, str, str, dict[str, Any]]]:
    s = h.scenario
    member = str(s.member.member_id)
    return [
        ("medecin_conseil", "POST", "/v1/joe/decision-drafts", {"claim_id": s.review_claim_id}),
        ("gestionnaire", "POST", "/v1/joe/questions", {"question": "Quels sont ses droits ?",
                                                       "member_id": member}),
        ("gestionnaire", "POST", "/v1/joe/questions", {"question": "Résume ce dossier",
                                                       "claim_id": s.review_claim_id}),
        ("medecin_conseil", "POST", "/v1/joe/questions", {
            "question": "Faut-il accorder ce dossier ? Historique et barème ?",
            "claim_id": s.review_claim_id}),
        ("gestionnaire", "POST", "/v1/joe/message-drafts", {"member_id": member,
                                                            "purpose": "relance_cotisation"}),
        ("admin", "POST", "/v1/joe/message-drafts", {"member_id": member,
                                                     "purpose": "confirmation_accord"}),
        ("gestionnaire", "GET", "/v1/search?q=Kouassi", {}),
        ("admin", "GET", "/v1/ai-actions", {}),
    ]  # fmt: skip


def test_aucune_operation_de_joe_ne_change_l_etat(harness: JoeHarness) -> None:
    seed, client = harness.seed, harness.client
    before = snapshot(seed, exclude=JOURNAL)
    journal_before = int(seed.scalar("SELECT count(*) FROM ai_actions"))

    for who, method, url, body in _calls(harness):
        if method == "POST":
            response = client.post(url, json=body, headers=seed.auth(who))
        else:
            response = client.get(url, headers=seed.auth(who))
        assert response.status_code == 200, (url, response.text)

    assert snapshot(seed, exclude=JOURNAL) == before
    assert int(seed.scalar("SELECT count(*) FROM ai_actions")) > journal_before


def test_une_recommandation_d_accorder_n_accorde_rien(harness: JoeHarness) -> None:
    seed, client, s = harness.seed, harness.client, harness.scenario
    before = snapshot(seed, exclude=JOURNAL)

    response = client.post(
        "/v1/joe/decision-drafts",
        json={"claim_id": s.review_claim_id},
        headers=seed.auth("medecin_conseil"),
    )

    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["applied"] is False
    assert draft["recommendation"] in {"accorder", "refuser", "demander_pieces"}
    assert snapshot(seed, exclude=JOURNAL) == before
    claim = s.review_claim_id
    assert seed.scalar("SELECT status FROM claims WHERE id = %s", (claim,)) == "en_revue"
    assert seed.scalar("SELECT count(*) FROM claim_decisions WHERE claim_id = %s", (claim,)) == 1
    assert seed.scalar("SELECT count(*) FROM authorizations WHERE claim_id = %s", (claim,)) == 0
    assert seed.scalar("SELECT count(*) FROM ledger_entries WHERE source_id = %s", (claim,)) == 0
    # Le journal garde la trace de la préparation, avec ses sources.
    row = seed.scalar(
        "SELECT sources FROM ai_actions WHERE id = %s AND kind = 'preparation'",
        (draft["ai_action_id"],),
    )
    assert {"type": "claim", "id": claim} in [{"type": x["type"], "id": x["id"]} for x in row]


@pytest.mark.parametrize("who", ["gestionnaire", "admin", "clinique_p1"])
def test_seul_le_medecin_conseil_obtient_un_brouillon_de_decision(
    harness: JoeHarness, who: str
) -> None:
    response = harness.client.post(
        "/v1/joe/decision-drafts",
        json={"claim_id": harness.scenario.review_claim_id},
        headers=harness.seed.auth(who),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-02"


def test_aucune_route_de_joe_ne_decide_ni_ne_paie(harness: JoeHarness) -> None:
    paths = harness.client.app.openapi()["paths"]  # type: ignore[attr-defined]
    joe_ops = {
        op["operationId"]: (path, method)
        for path, item in paths.items()
        for method, op in item.items()
        if op.get("operationId")
        in {"askJoe", "draftClaimDecision", "draftMessage", "search", "listAiActions"}
    }
    assert joe_ops == {
        "askJoe": ("/v1/joe/questions", "post"),
        "draftClaimDecision": ("/v1/joe/decision-drafts", "post"),
        "draftMessage": ("/v1/joe/message-drafts", "post"),
        "search": ("/v1/search", "get"),
        "listAiActions": ("/v1/ai-actions", "get"),
    }
    for path in paths:
        if path.startswith("/v1/joe"):
            assert not any(w in path for w in ("approve", "reject", "pay", "decide")), path
