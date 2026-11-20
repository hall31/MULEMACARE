"""Durcissement de la vérification ES256 des accords hors ligne (phase 4, voie 2).

La vérification est déléguée à ``cryptography`` (OpenSSL) : plus aucune arithmétique de courbe
écrite à la main. Ces tests complètent ``test_ecdsa.py`` (vecteur RFC 6979, inchangé) :
signatures malformées, valeurs r/s hors bornes, malléabilité, clés invalides.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from fastapi.testclient import TestClient

from api.claims import ecdsa
from api.claims.tests.conftest import ClaimsSeed
from api.claims.tests.flows import ITEMS_48000, identify
from api.claims.tests.support import TestDeviceKey, b64url
from api.claims.tests.test_offline import _accord, _register, _sync

MESSAGE = b'{"offline_ref":"fictif-durcissement"}'


def _pair() -> tuple[ec.EllipticCurvePrivateKey, ecdsa.PublicKey]:
    private = ec.generate_private_key(ec.SECP256R1())
    numbers = private.public_key().public_numbers()
    jwk = {
        "crv": "P-256",
        "kty": "EC",
        "x": b64url(numbers.x.to_bytes(32)),
        "y": b64url(numbers.y.to_bytes(32)),
    }
    return private, ecdsa.parse_public_jwk(json.dumps(jwk))


def _raw(private: ec.EllipticCurvePrivateKey, message: bytes) -> tuple[int, int]:
    r, s = decode_dss_signature(private.sign(message, ec.ECDSA(hashes.SHA256())))
    return r, s


def _rs(r: int, s: int) -> bytes:
    return r.to_bytes(32) + s.to_bytes(32)


# --- Délégation à la bibliothèque ---------------------------------------------------------------


def test_aucune_arithmetique_de_courbe_maison() -> None:
    for name in ("_add", "_mul", "_on_curve", "G", "A", "B"):
        assert not hasattr(ecdsa, name), f"{name} : arithmétique de courbe maison restante"


def test_la_verification_passe_par_cryptography(monkeypatch: pytest.MonkeyPatch) -> None:
    private, key = _pair()
    r, s = _raw(private, MESSAGE)
    assert ecdsa.verify_es256(key, MESSAGE, _rs(r, s))
    calls: list[tuple[bytes, bytes, str]] = []

    class Refusing:
        def verify(self, signature: bytes, data: bytes, algorithm: ec.ECDSA) -> None:
            assert isinstance(algorithm.algorithm, hashes.SHA256)
            calls.append((signature, data, algorithm.algorithm.name))
            raise InvalidSignature

    monkeypatch.setattr(ecdsa, "to_crypto_key", lambda _key: Refusing())
    assert not ecdsa.verify_es256(key, MESSAGE, _rs(r, s))
    assert calls == [(encode_dss_signature(r, s), MESSAGE, "sha256")]


def test_signature_de_cryptography_acceptee_et_liee_au_message() -> None:
    private, key = _pair()
    r, s = _raw(private, MESSAGE)
    assert ecdsa.verify_es256(key, MESSAGE, _rs(r, s))
    assert not ecdsa.verify_es256(key, MESSAGE + b" ", _rs(r, s))
    _, other = _pair()
    assert not ecdsa.verify_es256(other, MESSAGE, _rs(r, s))


def test_signature_sha384_refusee() -> None:
    private, key = _pair()
    r, s = decode_dss_signature(private.sign(MESSAGE, ec.ECDSA(hashes.SHA384())))
    assert not ecdsa.verify_es256(key, MESSAGE, _rs(r, s))


# --- Signatures malformées ----------------------------------------------------------------------


@pytest.mark.parametrize("size", [0, 1, 31, 32, 63, 65, 72, 128])
def test_signature_de_mauvaise_longueur_refusee(size: int) -> None:
    private, key = _pair()
    r, s = _raw(private, MESSAGE)
    good = _rs(r, s)
    signature = (good * 3)[:size]
    assert not ecdsa.verify_es256(key, MESSAGE, signature)


def test_signature_completee_de_zeros_refusee() -> None:
    """Encodage non canonique : r ou s précédé d'octets nuls garde la même valeur entière."""
    private, key = _pair()
    r, s = _raw(private, MESSAGE)
    good = _rs(r, s)
    assert not ecdsa.verify_es256(key, MESSAGE, good[:32] + b"\x00" + good[32:])
    assert not ecdsa.verify_es256(key, MESSAGE, b"\x00" + good)


def test_signature_der_refusee() -> None:
    """Seul le format JWS r‖s (64 octets) est accepté, jamais le DER d'OpenSSL."""
    private, key = _pair()
    der = private.sign(MESSAGE, ec.ECDSA(hashes.SHA256()))
    assert len(der) != 64
    assert not ecdsa.verify_es256(key, MESSAGE, der)


# --- Valeurs r/s hors bornes ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(lambda r, s: (0, s), id="r=0"),
        pytest.param(lambda r, s: (r, 0), id="s=0"),
        pytest.param(lambda r, s: (ecdsa.N, s), id="r=N"),
        pytest.param(lambda r, s: (r, ecdsa.N), id="s=N"),
        pytest.param(lambda r, s: (ecdsa.N + 1, s), id="r=N+1"),
        pytest.param(lambda r, s: (r, ecdsa.N + 1), id="s=N+1"),
        pytest.param(lambda r, s: (2**256 - 1, s), id="r=2^256-1"),
        pytest.param(lambda r, s: (r, 2**256 - 1), id="s=2^256-1"),
    ],
)
def test_r_ou_s_hors_bornes_refuse(bad: Any) -> None:  # noqa: ANN401 — fabrique paramétrée
    private, key = _pair()
    r, s = _raw(private, MESSAGE)
    r2, s2 = bad(r, s)
    assert not ecdsa.verify_es256(key, MESSAGE, _rs(r2, s2))


def test_bornes_controlees_avant_la_bibliotheque(monkeypatch: pytest.MonkeyPatch) -> None:
    """r ou s hors de [1, N-1] n'atteint jamais OpenSSL (défense en profondeur)."""
    private, key = _pair()
    r, s = _raw(private, MESSAGE)
    called: list[int] = []
    original = encode_dss_signature

    def spy(r_: int, s_: int) -> bytes:
        called.append(1)
        return original(r_, s_)

    monkeypatch.setattr(ecdsa, "encode_dss_signature", spy)
    assert not ecdsa.verify_es256(key, MESSAGE, _rs(ecdsa.N, s))
    assert not ecdsa.verify_es256(key, MESSAGE, _rs(r, 0))
    assert called == []


# --- Malléabilité --------------------------------------------------------------------------------


def test_malleabilite_s_haut_acceptee_par_la_primitive() -> None:
    """(r, N-s) est aussi valide en ECDSA ; WebCrypto ne normalise pas s (Q-L7-03), donc refuser
    les s « hauts » refuserait la moitié des accords légitimes. La malléabilité est neutralisée
    au niveau métier : l'idempotence porte sur (device_id, offline_ref), qui est SIGNÉ, jamais
    sur les octets de la signature (test suivant)."""
    private, key = _pair()
    r, s = _raw(private, MESSAGE)
    assert ecdsa.verify_es256(key, MESSAGE, _rs(r, ecdsa.N - s))
    assert not ecdsa.verify_es256(key, MESSAGE + b"x", _rs(r, ecdsa.N - s))


def test_jumeau_malleable_d_un_accord_ne_cree_aucun_second_dossier(
    client: TestClient, seed: ClaimsSeed
) -> None:
    key = TestDeviceKey.generate()
    device = _register(client, seed, key)
    member = seed.new_member()
    identification = identify(client, seed, member)
    accord = _accord(
        key, device, identification, member, items=ITEMS_48000, total=48000, covered=38400
    )
    seed.clock.advance(timedelta(minutes=30))
    first = _sync(client, seed, device, [accord])
    assert first.status_code == 200, first.text
    [result] = first.json()["results"]
    assert result["outcome"] == "confirmee"

    raw = ecdsa.b64url_decode(accord["signature"])
    r, s = int.from_bytes(raw[:32]), int.from_bytes(raw[32:])
    twin = {**accord, "signature": b64url(_rs(r, ecdsa.N - s))}
    replay = _sync(client, seed, device, [twin])
    assert replay.json()["results"] == [result]
    assert seed.scalar("SELECT count(*) FROM claims WHERE member_id = %s", (member.member_id,)) == 1


# --- Clés invalides ------------------------------------------------------------------------------


def _jwk(**fields: object) -> str:
    base: dict[str, object] = {"crv": "P-256", "kty": "EC"}
    base.update(fields)
    return json.dumps(base)


_X = b64url((1).to_bytes(32))


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("", id="vide"),
        pytest.param("[]", id="liste"),
        pytest.param('"chaine"', id="chaine"),
        pytest.param(_jwk(), id="sans-coordonnees"),
        pytest.param(_jwk(x=_X), id="sans-y"),
        pytest.param(_jwk(x=1, y=2), id="coordonnees-non-texte"),
        pytest.param(_jwk(x="!!", y="!!"), id="base64-invalide"),
        pytest.param(_jwk(x=b64url(bytes(32)), y=b64url(bytes(32))), id="origine"),
        pytest.param(_jwk(x=b64url(bytes(33)), y=b64url(bytes(33))), id="33-octets"),
        pytest.param(_jwk(crv="P-256K", x=_X, y=_X), id="secp256k1"),
        pytest.param(_jwk(kty="OKP", x=_X, y=_X), id="okp"),
        pytest.param(
            _jwk(x=b64url((2**256 - 1).to_bytes(32)), y=b64url((2**256 - 1).to_bytes(32))),
            id="hors-du-corps",
        ),
    ],
)
def test_cle_publique_invalide(raw: str) -> None:
    with pytest.raises(ecdsa.InvalidKeyError):
        ecdsa.parse_public_jwk(raw)


def test_jwk_portant_une_cle_privee_refuse() -> None:
    """Le serveur ne reçoit jamais de clé privée : un JWK avec ``d`` est refusé, pas ignoré."""
    private, _ = _pair()
    numbers = private.private_numbers()
    pub = numbers.public_numbers
    raw = _jwk(
        x=b64url(pub.x.to_bytes(32)),
        y=b64url(pub.y.to_bytes(32)),
        d=b64url(numbers.private_value.to_bytes(32)),
    )
    with pytest.raises(ecdsa.InvalidKeyError):
        ecdsa.parse_public_jwk(raw)


def test_public_point_reste_disponible_pour_le_signataire_de_test() -> None:
    private, key = _pair()
    d = private.private_numbers().private_value
    assert ecdsa.public_point(d) == (key.x, key.y)
    with pytest.raises(ValueError, match="scalaire"):
        ecdsa.public_point(ecdsa.N)
