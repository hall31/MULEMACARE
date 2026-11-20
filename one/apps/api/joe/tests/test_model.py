"""Interface LLM interne (sans SDK) : modèle configurable, déterministe par défaut, adaptateur
local-first optionnel limité à la boucle locale. R9 : aucune requête sortante avec donnée
identifiante ; sans configuration, aucune requête sortante du tout.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.claims.tests.conftest import ClaimsSeed
from api.integrations.egress import EgressAllowlist, EgressDeniedError, Endpoint, egress_guard
from api.integrations.transport import GuardedHttpTransport
from api.joe.model import (
    DeterministicModel,
    JoeModelSettings,
    LocalModel,
    ModelRequest,
    ModelUnavailableError,
    build_language_model,
)
from api.joe.tests.support import FakeLocalLlm, Scenario, build_client, build_scenario, leaks

REQUEST = ModelRequest(task="reponse", question="Droits ?", facts=("[ADH-1] : actif",),
                       draft="[ADH-1] : actif")  # fmt: skip


@pytest.fixture(scope="module")
def local_llm() -> Iterator[FakeLocalLlm]:
    with FakeLocalLlm() as server:
        yield server


@pytest.fixture(scope="module")
def local_setup(
    claims_seed: ClaimsSeed, local_llm: FakeLocalLlm
) -> Iterator[tuple[TestClient, Scenario]]:
    endpoint = Endpoint("127.0.0.1", local_llm.port)
    model = LocalModel(
        base_url=local_llm.base_url,
        model="modele-local-test",
        transport=GuardedHttpTransport(EgressAllowlist(frozenset({endpoint})), timeout_seconds=2),
    )
    with build_client(claims_seed, model, extra_endpoints=[endpoint]) as client:
        yield client, build_scenario(client, claims_seed)


def test_par_defaut_le_modele_est_deterministe_et_hors_reseau() -> None:
    settings = JoeModelSettings.from_env({})
    assert settings.kind == "deterministe"
    model = build_language_model(settings)
    assert isinstance(model, DeterministicModel)


def test_configuration_locale_lue_dans_l_environnement() -> None:
    settings = JoeModelSettings.from_env(
        {
            "MULEMA_JOE_MODEL": "local",
            "MULEMA_JOE_LOCAL_URL": "http://127.0.0.1:11434",
            "MULEMA_JOE_LOCAL_MODEL": "llama-local",
        }
    )
    model = build_language_model(settings)
    assert isinstance(model, LocalModel)
    assert model.name == "local:llama-local"


@pytest.mark.parametrize(
    "env",
    [
        {"MULEMA_JOE_MODEL": "openai"},
        {"MULEMA_JOE_MODEL": "local"},
        {"MULEMA_JOE_MODEL": "local", "MULEMA_JOE_LOCAL_URL": "http://127.0.0.1:11434"},
    ],
)
def test_configuration_invalide_refusee(env: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="MULEMA_JOE"):
        JoeModelSettings.from_env(env)


@pytest.mark.parametrize(
    "url", ["https://api.openai.com", "http://10.0.0.5:11434", "http://llm.example.test:80"]
)
def test_l_adaptateur_local_refuse_toute_adresse_hors_boucle_locale(url: str) -> None:
    transport = GuardedHttpTransport(EgressAllowlist(frozenset()), timeout_seconds=1)
    with pytest.raises(ValueError, match="boucle locale"):
        LocalModel(base_url=url, model="x", transport=transport)


def test_l_adaptateur_local_reste_soumis_a_la_garde_d_egress() -> None:
    """Même en boucle locale, la garde d'egress refuse une destination non listée."""
    transport = GuardedHttpTransport(EgressAllowlist(frozenset()), timeout_seconds=1)
    model = LocalModel(base_url="http://127.0.0.1:9", model="x", transport=transport)
    with pytest.raises(ModelUnavailableError) as info:
        asyncio.run(model.complete(REQUEST))
    assert isinstance(info.value.__cause__, EgressDeniedError)


def test_joe_repond_sans_aucun_acces_reseau(
    claims_seed: ClaimsSeed,
) -> None:
    """Modèle par défaut sous une garde qui refuse TOUT (même la boucle locale)."""
    with build_client(claims_seed, DeterministicModel()) as client:
        scenario = build_scenario(client, claims_seed)
        with egress_guard(EgressAllowlist(frozenset())):
            response = client.post(
                "/v1/joe/questions",
                json={"question": "Droits ?", "member_id": str(scenario.member.member_id)},
                headers=claims_seed.auth("gestionnaire"),
            )
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "reponse"


def test_requetes_vers_le_modele_local_sans_donnee_identifiante(
    local_setup: tuple[TestClient, Scenario], local_llm: FakeLocalLlm, claims_seed: ClaimsSeed
) -> None:
    client, scenario = local_setup
    start = len(local_llm.bodies)
    member = str(scenario.member.member_id)
    for who, url, body in [
        ("gestionnaire", "/v1/joe/questions",
         {"question": f"Droits de Aminata Kouassi-Fictive {scenario.member.member_number} ?",
          "member_id": member}),
        ("medecin_conseil", "/v1/joe/decision-drafts", {"claim_id": scenario.review_claim_id}),
        ("gestionnaire", "/v1/joe/message-drafts",
         {"member_id": member, "purpose": "relance_cotisation"}),
    ]:  # fmt: skip
        response = client.post(url, json=body, headers=claims_seed.auth(who))
        assert response.status_code == 200, response.text

    bodies = local_llm.bodies[start:]
    assert len(bodies) == 3
    for raw in bodies:
        text = raw.decode()
        assert leaks(text, scenario.identifying_values()) == [], text
        payload = json.loads(raw)
        assert payload["model"] == "modele-local-test"
        assert payload["stream"] is False


def test_la_reponse_du_modele_local_est_rehydratee_et_journalisee(
    local_setup: tuple[TestClient, Scenario], claims_seed: ClaimsSeed
) -> None:
    client, scenario = local_setup
    response = client.post(
        "/v1/joe/questions",
        json={"question": "Droits ?", "member_id": str(scenario.member.member_id)},
        headers=claims_seed.auth("gestionnaire"),
    )
    body = response.json()
    assert body["answer"] == f"Réponse du modèle local pour {scenario.member.member_number}."
    model = claims_seed.scalar(
        "SELECT model FROM ai_actions WHERE id = %s", (body["ai_action_id"],)
    )
    assert model == "local:modele-local-test"


def test_panne_du_modele_local_repli_deterministe(
    local_setup: tuple[TestClient, Scenario], local_llm: FakeLocalLlm, claims_seed: ClaimsSeed
) -> None:
    client, scenario = local_setup
    local_llm.state.fail_with = 500
    try:
        response = client.post(
            "/v1/joe/questions",
            json={"question": "Droits ?", "member_id": str(scenario.member.member_id)},
            headers=claims_seed.auth("gestionnaire"),
        )
    finally:
        local_llm.state.fail_with = None
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "reponse"
    assert body["sources"]
    model = claims_seed.scalar(
        "SELECT model FROM ai_actions WHERE id = %s", (body["ai_action_id"],)
    )
    assert model == DeterministicModel().name
