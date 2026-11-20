"""L10 — fournisseur d'identité OIDC : signature, émetteur, audience, temps, algorithme,
rotation des clés, revendications d'identité. Aucune requête réseau hors boucle locale."""

from __future__ import annotations

import asyncio
import base64
import json
import threading
import uuid
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization

from api.core.errors import NotAuthenticatedError
from api.core.identity import Identity, IdentityProvider
from api.core.oidc import (
    FileJwksSource,
    HttpJwksSource,
    OidcConfig,
    OidcIdentityProvider,
    TokenRejectedError,
)
from api.core.tests.oidc_keys import (
    AUDIENCE,
    ISSUER,
    FakeMonotonic,
    SigningKey,
    StaticJwks,
    claims,
    ec_key,
    rsa_key,
    sign,
)
from api.integrations.egress import EgressAllowlist, EgressDeniedError, Endpoint
from api.integrations.transport import GuardedHttpTransport

ORG = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
RSA = rsa_key("cle-rsa-1")
EC = ec_key("cle-ec-1")


def _provider(source: StaticJwks, monotonic: FakeMonotonic | None = None) -> OidcIdentityProvider:
    config = OidcConfig(issuer=ISSUER, audience=AUDIENCE)
    if monotonic is None:
        return OidcIdentityProvider(config, source)
    return OidcIdentityProvider(config, source, monotonic=monotonic)


def _reason(provider: OidcIdentityProvider, token: str) -> str:
    with pytest.raises(TokenRejectedError) as caught:
        asyncio.run(provider.authenticate(token))
    assert isinstance(caught.value, NotAuthenticatedError)  # rendu AUTH-01 par l'API
    return caught.value.reason


def _b64(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_le_fournisseur_respecte_l_interface() -> None:
    assert isinstance(_provider(StaticJwks([RSA])), IdentityProvider)


@pytest.mark.parametrize("key", [RSA, EC], ids=["RS256", "ES256"])
def test_jeton_valide_donne_sujet_et_organisation(key: SigningKey) -> None:
    provider = _provider(StaticJwks([RSA, EC]))
    identity = asyncio.run(provider.authenticate(sign(key, claims("sub-agent-1", ORG))))
    assert identity == Identity(subject="sub-agent-1", organization_id=ORG)


# --- Mutations de signature -------------------------------------------------------------------


def test_charge_utile_modifiee_refusee() -> None:
    header, _, signature = sign(RSA, claims("sub-a", ORG)).split(".")
    forged = _b64(claims("sub-admin", ORG))
    assert _reason(_provider(StaticJwks([RSA])), f"{header}.{forged}.{signature}") == "signature"


def test_signature_d_une_autre_cle_avec_le_meme_kid_refusee() -> None:
    impostor = rsa_key(RSA.kid)
    assert _reason(_provider(StaticJwks([RSA])), sign(impostor, claims("s", ORG))) == "signature"


# --- Mutations d'algorithme -------------------------------------------------------------------


def test_alg_none_refuse() -> None:
    token = f"{_b64({'alg': 'none', 'kid': RSA.kid, 'typ': 'JWT'})}.{_b64(claims('s', ORG))}."
    assert _reason(_provider(StaticJwks([RSA])), token) == "algorithme"


def test_confusion_hs256_avec_la_cle_publique_refusee() -> None:
    """Attaque classique : HMAC « signé » avec la clé publique RSA comme secret."""
    pem = RSA.private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    header = _b64({"alg": "HS256", "kid": RSA.kid, "typ": "JWT"})
    payload = _b64(claims("s", ORG))
    import hashlib  # noqa: PLC0415
    import hmac  # noqa: PLC0415

    mac = hmac.new(pem, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    token = f"{header}.{payload}.{base64.urlsafe_b64encode(mac).rstrip(b'=').decode()}"
    assert _reason(_provider(StaticJwks([RSA])), token) == "algorithme"


def test_algorithme_hors_liste_refuse() -> None:
    token = jwt.encode(claims("s", ORG), RSA.private, algorithm="RS512", headers={"kid": RSA.kid})
    assert _reason(_provider(StaticJwks([RSA])), token) == "algorithme"


def test_es256_annonce_avec_une_cle_rsa_refuse() -> None:
    """``alg`` d'en-tête cohérent avec la liste, mais pas avec la clé désignée par ``kid``."""
    token = sign(EC, claims("s", ORG), headers={"kid": RSA.kid})
    assert _reason(_provider(StaticJwks([RSA, EC])), token) == "algorithme_de_cle"


def test_liste_restreinte_a_es256_refuse_rs256() -> None:
    provider = OidcIdentityProvider(
        OidcConfig(issuer=ISSUER, audience=AUDIENCE, algorithms=frozenset({"ES256"})),
        StaticJwks([RSA, EC]),
    )
    assert _reason(provider, sign(RSA, claims("s", ORG))) == "algorithme"


def test_configuration_refuse_hmac_et_none() -> None:
    for algorithms in ({"HS256"}, {"none"}, {"RS256", "HS256"}, set()):
        with pytest.raises(ValueError, match="algorithmes"):
            OidcConfig(issuer=ISSUER, audience=AUDIENCE, algorithms=frozenset(algorithms))


def test_cle_symetrique_publiee_dans_le_jwks_ignoree() -> None:
    source = StaticJwks()
    provider = _provider(source)
    oct_key = {"kty": "oct", "kid": "partage", "k": _b64({"x": 1}), "alg": "HS256"}

    async def fetch() -> dict[str, Any]:
        return {"keys": [oct_key]}

    source.fetch = fetch  # type: ignore[method-assign]
    token = jwt.encode(claims("s", ORG), b"x" * 32, algorithm="HS256", headers={"kid": "partage"})
    assert _reason(provider, token) == "algorithme"


# --- Mutations d'émetteur, d'audience et de temps ---------------------------------------------


def test_audience_differente_refusee() -> None:
    token = sign(RSA, claims("s", ORG, aud="une-autre-api"))
    assert _reason(_provider(StaticJwks([RSA])), token) == "audience"


def test_emetteur_different_refuse() -> None:
    token = sign(RSA, claims("s", ORG, iss="https://idp.ailleurs.invalid"))
    assert _reason(_provider(StaticJwks([RSA])), token) == "emetteur"


def test_jeton_expire_refuse_au_dela_de_la_tolerance() -> None:
    payload = claims("s", ORG)
    payload["exp"] = payload["iat"] - 61  # tolérance par défaut : 60 s
    assert _reason(_provider(StaticJwks([RSA])), sign(RSA, payload)) == "expire"


def test_tolerance_d_horloge_admise() -> None:
    payload = claims("s", ORG)
    payload["exp"] = payload["iat"] - 30
    identity = asyncio.run(_provider(StaticJwks([RSA])).authenticate(sign(RSA, payload)))
    assert identity.subject == "s"


def test_pas_avant_dans_le_futur_refuse() -> None:
    payload = claims("s", ORG)
    payload["nbf"] = payload["iat"] + 600
    assert _reason(_provider(StaticJwks([RSA])), sign(RSA, payload)) == "pas_encore_valide"


def test_emis_dans_le_futur_refuse() -> None:
    payload = claims("s", ORG)
    payload["iat"] += 600
    payload["exp"] += 600
    assert _reason(_provider(StaticJwks([RSA])), sign(RSA, payload)) == "pas_encore_valide"


@pytest.mark.parametrize("missing", ["exp", "iat", "iss", "aud", "sub"])
def test_revendication_obligatoire_absente_refusee(missing: str) -> None:
    payload = claims("s", ORG)
    del payload[missing]
    assert _reason(_provider(StaticJwks([RSA])), sign(RSA, payload)) == "invalide"


# --- Identité One -----------------------------------------------------------------------------


@pytest.mark.parametrize("value", [None, "pas-un-uuid", 42])
def test_organisation_absente_ou_invalide_refusee(value: object) -> None:
    payload = claims("s", ORG)
    if value is None:
        del payload["mulema_org"]
    else:
        payload["mulema_org"] = value
    assert _reason(_provider(StaticJwks([RSA])), sign(RSA, payload)) == "organisation"


def test_revendication_d_organisation_configurable() -> None:
    provider = OidcIdentityProvider(
        OidcConfig(issuer=ISSUER, audience=AUDIENCE, organization_claim="org"),
        StaticJwks([RSA]),
    )
    token = sign(RSA, claims("s", ORG, org=str(ORG)) | {"mulema_org": "ignore"})
    assert asyncio.run(provider.authenticate(token)).organization_id == ORG


def test_jeton_illisible_ou_trop_long_refuse() -> None:
    provider = _provider(StaticJwks([RSA]))
    assert _reason(provider, "pas.un.jwt") == "format"
    assert _reason(provider, "a" * 9000) == "format"


def test_kid_absent_refuse() -> None:
    token = jwt.encode(claims("s", ORG), RSA.private, algorithm="RS256")
    assert _reason(_provider(StaticJwks([RSA])), token) == "kid_absent"


# --- Rotation et cache ------------------------------------------------------------------------


def test_rotation_nouvelle_cle_acceptee_apres_relecture() -> None:
    source = StaticJwks([RSA])
    clock = FakeMonotonic()
    provider = _provider(source, monotonic=clock)
    asyncio.run(provider.authenticate(sign(RSA, claims("s", ORG))))
    assert source.fetches == 1
    fresh = ec_key()
    source.keys.append(fresh)
    clock.value += 31  # au-delà de l'intervalle minimal de relecture
    asyncio.run(provider.authenticate(sign(fresh, claims("s", ORG))))
    assert source.fetches == 2


def test_kid_inconnu_ne_force_pas_une_relecture_a_chaque_requete() -> None:
    source = StaticJwks([RSA])
    provider = _provider(source, monotonic=FakeMonotonic())
    unknown = rsa_key("kid-invente")
    for _ in range(5):
        assert _reason(provider, sign(unknown, claims("s", ORG))) == "kid_inconnu"
    assert source.fetches == 1


def test_cle_retiree_refusee_apres_expiration_du_cache() -> None:
    source = StaticJwks([RSA])
    clock = FakeMonotonic()
    provider = _provider(source, monotonic=clock)
    asyncio.run(provider.authenticate(sign(RSA, claims("s", ORG))))
    source.keys = [ec_key()]  # RSA retirée par l'émetteur (compromission, rotation)
    clock.value += 601
    assert _reason(provider, sign(RSA, claims("s", ORG))) == "kid_inconnu"


def test_jwks_injoignable_apres_expiration_refuse_tout() -> None:
    source = StaticJwks([RSA])
    clock = FakeMonotonic()
    provider = _provider(source, monotonic=clock)
    asyncio.run(provider.authenticate(sign(RSA, claims("s", ORG))))
    source.failing = True
    clock.value += 601
    assert _reason(provider, sign(RSA, claims("s", ORG))) == "jwks_indisponible"


def test_jwks_injoignable_avant_expiration_garde_les_cles() -> None:
    source = StaticJwks([RSA])
    clock = FakeMonotonic()
    provider = _provider(source, monotonic=clock)
    asyncio.run(provider.authenticate(sign(RSA, claims("s", ORG))))
    source.failing = True
    clock.value += 100
    asyncio.run(provider.authenticate(sign(RSA, claims("s", ORG))))


# --- Sources JWKS -----------------------------------------------------------------------------


def test_source_fichier_monte(tmp_path: Path) -> None:
    path = tmp_path / "jwks.json"
    path.write_text(json.dumps({"keys": [EC.public_jwk()]}), encoding="utf-8")
    provider = OidcIdentityProvider(
        OidcConfig(issuer=ISSUER, audience=AUDIENCE), FileJwksSource(path)
    )
    assert asyncio.run(provider.authenticate(sign(EC, claims("s", ORG)))).organization_id == ORG


@pytest.fixture
def jwks_server() -> Iterator[int]:
    body = json.dumps({"keys": [RSA.public_jwk()]}).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def test_source_http_par_le_transport_garde(jwks_server: int) -> None:
    allowlist = EgressAllowlist(frozenset({Endpoint("127.0.0.1", jwks_server)}))
    source = HttpJwksSource(
        f"http://127.0.0.1:{jwks_server}/jwks", GuardedHttpTransport(allowlist, timeout_seconds=2)
    )
    provider = OidcIdentityProvider(OidcConfig(issuer=ISSUER, audience=AUDIENCE), source)
    assert asyncio.run(provider.authenticate(sign(RSA, claims("s", ORG)))).subject == "s"


def test_source_http_hors_liste_blanche_ne_sort_pas(jwks_server: int) -> None:
    source = HttpJwksSource(
        f"http://127.0.0.1:{jwks_server}/jwks",
        GuardedHttpTransport(EgressAllowlist(frozenset()), timeout_seconds=2),
    )
    with pytest.raises(EgressDeniedError):
        asyncio.run(source.fetch())
