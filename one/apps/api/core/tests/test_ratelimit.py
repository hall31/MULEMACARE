"""L10 — limitation de débit : seau à jetons, clés IP et jeton, 429 RATE-01 sur les opérations
publiques, la mesure produit (Q-P2-07) et l'identification au comptoir.

Application assemblée SANS base (lifespan non démarré) : le refus 429 intervient AVANT la route,
donc avant toute base ; les demandes admises échouent ensuite faute de base (500), ce qui suffit
à prouver qu'elles ont passé le limiteur.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from api.core.ratelimit import (
    DEFAULT_RULES,
    InMemoryRateLimitStore,
    Limit,
    RateLimits,
    RateRule,
    client_ip,
    missing_operations,
    parse_trusted_proxies,
    token_fingerprint,
)
from api.core.tests.oidc_keys import FakeMonotonic
from api.tests.e2e.test_mounted_operations import assembled_app

TOO_MANY = 429
TOKEN_LEN = 43


def _acquire(store: InMemoryRateLimitStore, key: str, limit: Limit) -> float:
    return asyncio.run(store.acquire(key, limit))


# --- Seau à jetons ----------------------------------------------------------------------------


def test_seau_admet_la_capacite_puis_refuse_avec_delai() -> None:
    clock = FakeMonotonic()
    store = InMemoryRateLimitStore(now=clock)
    limit = Limit(3, 60)
    assert [_acquire(store, "k", limit) for _ in range(3)] == [0, 0, 0]
    assert _acquire(store, "k", limit) == pytest.approx(20.0)
    clock.value += 20
    assert _acquire(store, "k", limit) == 0
    assert _acquire(store, "k", limit) > 0


def test_seaux_independants_par_cle() -> None:
    store = InMemoryRateLimitStore(now=FakeMonotonic())
    limit = Limit(1, 60)
    assert _acquire(store, "a", limit) == 0
    assert _acquire(store, "a", limit) > 0
    assert _acquire(store, "b", limit) == 0


def test_memoire_bornee() -> None:
    store = InMemoryRateLimitStore(max_keys=10, now=FakeMonotonic())
    for i in range(50):
        _acquire(store, f"k{i}", Limit(1))
    assert len(store) == 10


def test_limite_invalide_refusee() -> None:
    with pytest.raises(ValueError, match="limite"):
        Limit(0)


# --- Clés -------------------------------------------------------------------------------------


def _scope(peer: str, *headers: tuple[bytes, bytes]) -> dict[str, object]:
    return {"type": "http", "client": (peer, 1234), "headers": list(headers)}


def test_x_forwarded_for_ignore_sans_mandataire_de_confiance() -> None:
    scope = _scope("203.0.113.9", (b"x-forwarded-for", b"198.51.100.1"))
    assert client_ip(scope, ()) == "203.0.113.9"


def test_x_forwarded_for_lu_de_droite_a_gauche_derriere_un_mandataire() -> None:
    trusted = parse_trusted_proxies("10.0.0.0/8, 192.0.2.1")
    # Le client a forgé « 1.2.3.4 » à gauche ; le mandataire a ajouté sa vraie adresse.
    scope = _scope("10.0.0.5", (b"x-forwarded-for", b"1.2.3.4, 198.51.100.7, 192.0.2.1"))
    assert client_ip(scope, trusted) == "198.51.100.7"


def test_empreinte_du_jeton_jamais_le_jeton() -> None:
    token = uuid.uuid4().hex  # jeton fictif généré
    fingerprint = token_fingerprint(_scope("x", (b"authorization", f"Bearer {token}".encode())))
    assert fingerprint is not None
    assert token not in fingerprint
    assert token_fingerprint(_scope("x")) is None


# --- Application assemblée --------------------------------------------------------------------


def _client(rules: dict[str, RateRule], **kwargs: object) -> TestClient:
    limits = RateLimits(rules=DEFAULT_RULES | rules, store=InMemoryRateLimitStore())
    return TestClient(assembled_app(limits), raise_server_exceptions=False, **kwargs)  # type: ignore[arg-type]


def _assert_429(response: object) -> None:
    status = getattr(response, "status_code", None)
    assert status == TOO_MANY
    body = response.json()  # type: ignore[attr-defined]
    assert body["code"] == "RATE-01"
    assert body["retry_after_seconds"] >= 1
    assert body["request_id"] == response.headers["X-Request-ID"]  # type: ignore[attr-defined]
    assert response.headers["Retry-After"] == str(body["retry_after_seconds"])  # type: ignore[attr-defined]
    assert response.headers["content-type"].startswith("application/problem+json")  # type: ignore[attr-defined]


def test_toutes_les_operations_limitees_sont_montees() -> None:
    assert missing_operations(assembled_app().routes, DEFAULT_RULES) == []
    assert set(DEFAULT_RULES) >= {
        "getOrganizationBranding",
        "getPublicPaymentLink",
        "startCheckout",
        "receivePaymentWebhook",
        "recordProductEvent",
        "startIdentification",
        "sendIdentificationCode",
        "verifyIdentificationCode",
    }


def test_regle_sans_route_refuse_l_assemblage() -> None:
    with pytest.raises(RuntimeError, match="operationInexistante"):
        assembled_app(RateLimits(rules={"operationInexistante": RateRule(per_ip=Limit(1))}))


PUBLIC_CALLS = [
    ("getOrganizationBranding", "GET", "/v1/public/branding?slug=mulemacare-ci-demo"),
    ("getPublicPaymentLink", "GET", f"/v1/public/payment-links/{'t' * 40}"),
    ("startCheckout", "POST", f"/v1/public/payment-links/{'t' * 40}/checkout"),
    ("receivePaymentWebhook", "POST", "/v1/webhooks/mulemacare-ci-demo/payments/wave"),
]


@pytest.mark.parametrize(("operation", "method", "path"), PUBLIC_CALLS)
def test_endpoint_public_limite_par_ip(operation: str, method: str, path: str) -> None:
    client = _client({operation: RateRule(per_ip=Limit(2))})
    for _ in range(2):
        assert client.request(method, path).status_code != TOO_MANY
    _assert_429(client.request(method, path))
    # Autre adresse : son propre seau.
    other = _client({operation: RateRule(per_ip=Limit(2))}, client=("198.51.100.20", 4000))
    assert other.request(method, path).status_code != TOO_MANY


@pytest.mark.parametrize(
    ("operation", "path"),
    [
        ("recordProductEvent", "/v1/telemetry/events"),
        ("startIdentification", "/v1/counter/identifications"),
        ("sendIdentificationCode", f"/v1/counter/identifications/{uuid.uuid4()}/code"),
        (
            "verifyIdentificationCode",
            f"/v1/counter/identifications/{uuid.uuid4()}/code-verification",
        ),
    ],
)
def test_limite_par_jeton(operation: str, path: str) -> None:
    client = _client({operation: RateRule(per_ip=Limit(100), per_token=Limit(2))})
    first = {"Authorization": "Bearer " + "a" * TOKEN_LEN}
    second = {"Authorization": "Bearer " + "b" * TOKEN_LEN}
    for _ in range(2):
        assert client.post(path, headers=first, json={}).status_code != TOO_MANY
    _assert_429(client.post(path, headers=first, json={}))
    assert client.post(path, headers=second, json={}).status_code != TOO_MANY


def test_rotation_de_jetons_freinee_par_la_limite_ip() -> None:
    client = _client({"recordProductEvent": RateRule(per_ip=Limit(3), per_token=Limit(100))})
    codes = [
        client.post(
            "/v1/telemetry/events", headers={"Authorization": f"Bearer jeton-{i}"}, json={}
        ).status_code
        for i in range(4)
    ]
    assert codes[-1] == TOO_MANY
    assert TOO_MANY not in codes[:3]


def test_operation_non_limitee_jamais_refusee() -> None:
    client = _client({"getOrganizationBranding": RateRule(per_ip=Limit(1))})
    for _ in range(5):
        assert client.get("/healthz").status_code == 200
        assert client.get("/v1/me").status_code != TOO_MANY


def test_refus_journalise_sans_ip_ni_jeton(caplog: pytest.LogCaptureFixture) -> None:
    client = _client({"recordProductEvent": RateRule(per_token=Limit(1))})
    headers = {"Authorization": "Bearer jeton-journal"}
    with caplog.at_level(logging.WARNING, logger="mulema"):
        client.post("/v1/telemetry/events", headers=headers, json={})
        client.post("/v1/telemetry/events", headers=headers, json={})
    refused = [r for r in caplog.records if r.msg == "ratelimit.refused"]
    assert len(refused) == 1
    fields = refused[0].fields  # type: ignore[attr-defined]
    assert fields == {"operation": "recordProductEvent", "dimension": "jeton"}
