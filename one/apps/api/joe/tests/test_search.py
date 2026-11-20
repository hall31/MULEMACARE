"""Recherche ⌘K : adhérents, dossiers et prestataires VISIBLES par l'utilisateur (R10)."""

from __future__ import annotations

from typing import Any

import pytest

from api.joe.search import EXAMPLE_QUESTIONS
from api.joe.tests.support import FAMILY_NAME, JoeHarness


def _search(h: JoeHarness, who: str, q: str) -> list[dict[str, Any]]:
    response = h.client.get("/v1/search", params={"q": q}, headers=h.seed.auth(who))
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


def _hits(items: list[dict[str, Any]], kind: str) -> set[str]:
    return {i["id"] for i in items if i["type"] == kind}


def test_le_gestionnaire_trouve_l_adherent_par_nom_et_par_numero(harness: JoeHarness) -> None:
    s = harness.scenario
    member = str(s.member.member_id)
    assert member in _hits(_search(harness, "gestionnaire", FAMILY_NAME[:7]), "member")
    assert member in _hits(_search(harness, "gestionnaire", s.member.member_number), "member")


def test_dossier_par_numero_et_prestataire_par_nom(harness: JoeHarness) -> None:
    s, seed = harness.scenario, harness.seed
    items = _search(harness, "gestionnaire", s.review_claim_number)
    assert s.review_claim_id in _hits(items, "claim")
    hit = next(i for i in items if i["id"] == s.review_claim_id)
    assert hit["label"] == s.review_claim_number
    assert hit["meta"] == "en_revue"
    providers = _hits(_search(harness, "medecin_conseil", "fictive P1"), "provider")
    assert str(seed.providers["p1"]) in providers


def test_la_clinique_ne_voit_que_ses_dossiers_et_aucun_adherent(harness: JoeHarness) -> None:
    s, seed = harness.scenario, harness.seed
    assert s.review_claim_id in _hits(_search(harness, "clinique_p1", "PEC-"), "claim")
    assert s.review_claim_id not in _hits(_search(harness, "clinique_p2", "PEC-"), "claim")
    assert _hits(_search(harness, "clinique_p1", FAMILY_NAME[:7]), "member") == set()
    providers = _hits(_search(harness, "clinique_p2", "Clinique fictive"), "provider")
    assert providers == {str(seed.providers["p2"])}


def test_le_medecin_conseil_ne_cherche_pas_les_adherents(harness: JoeHarness) -> None:
    assert _hits(_search(harness, "medecin_conseil", FAMILY_NAME[:7]), "member") == set()


@pytest.mark.parametrize("who", ["gestionnaire_b", "clinique_b"])
def test_isolation_rien_de_l_organisation_a(harness: JoeHarness, who: str) -> None:
    s = harness.scenario
    ids = {i["id"] for i in _search(harness, who, "Clinique")}
    ids |= {i["id"] for i in _search(harness, who, s.review_claim_number)}
    ids |= {i["id"] for i in _search(harness, who, FAMILY_NAME[:7])}
    assert s.review_claim_id not in ids
    assert str(s.member.member_id) not in ids
    assert str(harness.seed.providers["p1"]) not in ids


def test_les_jokers_sont_echappes(harness: JoeHarness) -> None:
    assert _search(harness, "gestionnaire", "%%") == []
    assert _search(harness, "gestionnaire", "__") == []


@pytest.mark.parametrize("q", ["a", "x" * 201])
def test_longueur_de_requete_validee(harness: JoeHarness, q: str) -> None:
    response = harness.client.get(
        "/v1/search", params={"q": q}, headers=harness.seed.auth("gestionnaire")
    )
    assert response.status_code == 422


def test_sans_jeton_401(harness: JoeHarness) -> None:
    assert harness.client.get("/v1/search", params={"q": "PEC"}).status_code == 401


def test_questions_d_exemple_sans_donnee_medicale() -> None:
    assert len(EXAMPLE_QUESTIONS) >= 4
    for question in EXAMPLE_QUESTIONS:
        lowered = question.lower()
        assert not any(w in lowered for w in ("motif", "diagnostic", "ordonnance", "maladie"))
