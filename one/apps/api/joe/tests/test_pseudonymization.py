"""R9/R11 — aucune donnée identifiante n'est envoyée au modèle.

Le modèle espion garde chaque requête : on y cherche le nom, le téléphone, le numéro
d'adhérent, la date de naissance et tout UUID interne, même quand l'utilisateur les tape dans
sa question.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from api.joe.model import DeterministicModel, ModelRequest
from api.joe.pseudonym import (
    IdentifyingDataError,
    ModelGateway,
    Pseudonymizer,
    asks_medical,
    mask_question,
)
from api.joe.tests.support import FAMILY_NAME, GIVEN_NAME, JoeHarness, SpyModel, leaks


def _prompts(spy: SpyModel, start: int) -> list[str]:
    return [r.prompt() for r in spy.requests[start:]]


def test_aucune_donnee_identifiante_vers_le_modele(harness: JoeHarness) -> None:
    s, seed, spy = harness.scenario, harness.seed, harness.spy
    member = str(s.member.member_id)
    start = len(spy.requests)
    question = (
        f"Quels sont les droits et l'historique de {GIVEN_NAME} {FAMILY_NAME}, "
        f"carte {s.member.member_number}, tél {s.member.phone} ?"
    )
    calls = [
        ("gestionnaire", "/v1/joe/questions", {"question": question, "member_id": member}),
        ("gestionnaire", "/v1/joe/questions", {"question": f"Cotisations de {FAMILY_NAME} ?",
                                               "member_id": member}),
        ("admin", "/v1/joe/questions", {"question": "Résumé", "claim_id": s.review_claim_id}),
        ("medecin_conseil", "/v1/joe/decision-drafts", {"claim_id": s.review_claim_id}),
        ("gestionnaire", "/v1/joe/message-drafts", {"member_id": member,
                                                    "purpose": "relance_cotisation"}),
    ]  # fmt: skip
    for who, url, body in calls:
        response = harness.client.post(url, json=body, headers=seed.auth(who))
        assert response.status_code == 200, response.text

    prompts = _prompts(spy, start)
    assert len(prompts) == len(calls)
    for prompt in prompts:
        assert leaks(prompt, s.identifying_values()) == [], prompt
    # Le modèle a bien reçu des faits (jetons), pas une requête vide.
    assert any("[ADH-1]" in p for p in prompts)


def test_la_reponse_rehydrate_les_jetons_sans_nom(harness: JoeHarness) -> None:
    s = harness.scenario
    response = harness.client.post(
        "/v1/joe/questions",
        json={"question": "Droits ?", "member_id": str(s.member.member_id)},
        headers=harness.seed.auth("gestionnaire"),
    )
    answer = response.json()["answer"]
    assert "[ADH-" not in answer
    assert s.member.member_number in answer
    assert GIVEN_NAME not in answer
    assert FAMILY_NAME not in answer


def test_masquage_de_la_question() -> None:
    pz = Pseudonymizer()
    pz.forbid("Mariam", "Traoré-Fictive")
    masked = mask_question(
        "Droits de Mariam Traoré-Fictive, MC-00012345, +2250701020304, 07 01 02 03 04, "
        "mariam@exemple.test, née le 1990-05-06 ? Et Yao Konan ?",
        pz,
    )
    for needle in ("Mariam", "Traoré", "MC-00012345", "0701020304", "07 01 02 03 04",
                   "mariam@", "1990-05-06", "Yao", "Konan"):  # fmt: skip
        assert needle not in masked, masked
    assert masked.startswith("Droits de")


def test_le_controle_final_refuse_une_valeur_identifiante() -> None:
    pz = Pseudonymizer()
    pz.forbid("Aïcha")
    with pytest.raises(IdentifyingDataError):
        pz.check("Statut de aïcha : actif")
    with pytest.raises(IdentifyingDataError):
        pz.check(f"Dossier {uuid4()}")
    with pytest.raises(IdentifyingDataError):
        pz.check("Appeler le +22507010203")
    with pytest.raises(IdentifyingDataError):
        pz.check("Carte MC-00000001")
    pz.check("[ADH-1] : statut actif, plafond 3 000 000 FCFA, reste 2 952 000 FCFA.")


def test_la_passerelle_echoue_fermee_sans_appeler_le_modele() -> None:
    """Une fuite (bug d'outil) : le modèle n'est PAS appelé, repli déterministe local."""
    spy = SpyModel()
    pz = Pseudonymizer()
    pz.forbid("Aïcha")
    request = ModelRequest(
        task="reponse", question="Droits ?", facts=("Aïcha : actif",), draft="Aïcha : actif"
    )
    gateway = ModelGateway(spy, fallback=DeterministicModel())

    result = asyncio.run(gateway.complete(request, pz))

    assert spy.requests == []
    assert result.model == DeterministicModel().name
    assert result.blocked is True


@pytest.mark.parametrize(
    ("question", "medical"),
    [
        ("Quel est le motif ?", True),
        ("Diagnostic du patient", True),
        ("Une ordonnance ?", True),
        ("Quelle pathologie ?", True),
        ("Raison médicale de la visite", True),
        ("Quels sont ses droits ?", False),
        ("Faut-il accorder ce dossier ?", False),
        ("Historique des prises en charge", False),
    ],
)
def test_detection_des_questions_medicales(question: str, medical: bool) -> None:
    assert asks_medical(question) is medical
