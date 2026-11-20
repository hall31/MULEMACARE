"""Vérification ES256 (ECDSA P-256 / SHA-256) sans dépendance : vecteur RFC 6979 A.2.5."""

from __future__ import annotations

import pytest

from api.claims import ecdsa
from api.claims.tests.support import TestDeviceKey, b64url

# RFC 6979, A.2.5 (P-256), clé privée et signature SHA-256 du message « sample ».
RFC_X = 0xC9AFA9D845BA75166B5C215767B1D6934E50C3DB36E89B127B8A622B120F6721
RFC_UX = 0x60FED4BA255A9D31C961EB74C6356D68C049B8923B61FA6CE669622E60F29FB6
RFC_UY = 0x7903FE1008B8BC99A41AE9E95628BC64F2F1B20C2D7E9F5177A3C294D4462299
RFC_R = 0xEFD48B2AACB6A8FD1140DD9CD45E81D69D2C877B56AAF991C34D0EA84EAF3716
RFC_S = 0xF7CB1C942D657C41D436C7A1B6E29F65F3E900DBB9AFF4064DC4AB2F843ACDA8


def _jwk(x: int, y: int) -> str:
    return (
        f'{{"crv":"P-256","kty":"EC","x":"{b64url(x.to_bytes(32))}",'
        f'"y":"{b64url(y.to_bytes(32))}"}}'
    )


def test_vecteur_rfc6979() -> None:
    assert ecdsa.public_point(RFC_X) == (RFC_UX, RFC_UY)
    key = ecdsa.parse_public_jwk(_jwk(RFC_UX, RFC_UY))
    signature = RFC_R.to_bytes(32) + RFC_S.to_bytes(32)
    assert ecdsa.verify_es256(key, b"sample", signature)
    assert not ecdsa.verify_es256(key, b"samplf", signature)
    assert not ecdsa.verify_es256(key, b"sample", signature[:-1] + b"\x00")


def test_signature_hors_bornes_refusee() -> None:
    key = ecdsa.parse_public_jwk(_jwk(RFC_UX, RFC_UY))
    assert not ecdsa.verify_es256(key, b"sample", bytes(64))
    assert not ecdsa.verify_es256(key, b"sample", ecdsa.N.to_bytes(32) + RFC_S.to_bytes(32))
    assert not ecdsa.verify_es256(key, b"sample", b"court")


def test_aller_retour_avec_cle_de_test() -> None:
    device = TestDeviceKey.generate()
    key = ecdsa.parse_public_jwk(device.public_jwk)
    message = b'{"offline_ref":"fictif"}'
    signature = ecdsa.b64url_decode(device.sign(message))
    assert ecdsa.verify_es256(key, message, signature)


@pytest.mark.parametrize(
    "raw",
    [
        "pas du json",
        '{"kty":"RSA"}',
        '{"crv":"P-384","kty":"EC","x":"AA","y":"AA"}',
        _jwk(RFC_UX, RFC_UY + 1),  # hors de la courbe
        _jwk(ecdsa.P, 1),
    ],
)
def test_cle_invalide(raw: str) -> None:
    with pytest.raises(ecdsa.InvalidKeyError):
        ecdsa.parse_public_jwk(raw)
