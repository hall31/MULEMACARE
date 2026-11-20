"""Vérification ES256 (ECDSA P-256, SHA-256) des accords hors ligne, déléguée à ``cryptography``.

Aucune arithmétique de courbe n'est écrite ici (phase 4, voie 2) : la validation du point et la
vérification de la signature sont faites par OpenSSL via ``cryptography`` (specs/DEPENDENCIES.md).
Ce module ne fait que traduire le format du comptoir et refuser tôt ce qui n'en est pas.

Format (comptoir L7, Q-L7-03) : clé publique JWK ``{"kty":"EC","crv":"P-256","x","y"}`` (jamais
de ``d`` : le serveur ne reçoit aucune clé privée), signature = 64 octets r‖s (format JWS /
WebCrypto) en base64url. Le DER d'OpenSSL n'est pas accepté. Les s « hauts » sont acceptés :
WebCrypto ne normalise pas s, et la malléabilité est sans effet métier (l'idempotence porte sur
``offline_ref``, qui est signé). Contrôlé par le vecteur de la RFC 6979 (A.2.5).
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

# Caractéristique du corps et ordre du groupe de P-256 (SEC 2) : bornes de contrôle seulement.
P: Final = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
N: Final = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
_COORD_BYTES: Final = 32
_CURVE: Final = ec.SECP256R1()
_ALGORITHM: Final = ec.ECDSA(hashes.SHA256())


class InvalidKeyError(ValueError):
    """Clé publique illisible, d'un autre algorithme, privée ou hors de la courbe P-256."""


@dataclass(frozen=True, slots=True)
class PublicKey:
    x: int
    y: int


def b64url_decode(text: str) -> bytes:
    """Base64url sans remplissage ; lève ``ValueError`` si le texte n'en est pas."""
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("base64url invalide") from exc


def to_crypto_key(key: PublicKey) -> ec.EllipticCurvePublicKey:
    """Clé ``cryptography`` ; lève ``ValueError`` si le point n'est pas sur P-256."""
    return ec.EllipticCurvePublicNumbers(key.x, key.y, _CURVE).public_key()


def public_point(scalar: int) -> tuple[int, int]:
    """``scalar · G`` (sert au signataire de test et à l'auto-contrôle du vecteur RFC 6979)."""
    if not 0 < scalar < N:
        raise ValueError("scalaire nul ou hors de [1, N-1]")
    numbers = ec.derive_private_key(scalar, _CURVE).public_key().public_numbers()
    return numbers.x, numbers.y


def parse_public_jwk(raw: str) -> PublicKey:
    """JWK EC P-256 → point validé sur la courbe par ``cryptography`` (cofacteur 1)."""
    try:
        jwk = json.loads(raw)
    except ValueError as exc:
        raise InvalidKeyError("clé publique : JSON illisible") from exc
    if not isinstance(jwk, dict) or jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise InvalidKeyError("clé publique : EC P-256 attendue")
    if "d" in jwk:
        raise InvalidKeyError("clé publique : une clé privée ne doit jamais être envoyée")
    x_text, y_text = jwk.get("x"), jwk.get("y")
    if not isinstance(x_text, str) or not isinstance(y_text, str):
        raise InvalidKeyError("clé publique : coordonnées illisibles")
    try:
        xb, yb = b64url_decode(x_text), b64url_decode(y_text)
    except ValueError as exc:
        raise InvalidKeyError("clé publique : coordonnées illisibles") from exc
    if len(xb) != _COORD_BYTES or len(yb) != _COORD_BYTES:
        raise InvalidKeyError("clé publique : coordonnées de 32 octets attendues")
    key = PublicKey(int.from_bytes(xb), int.from_bytes(yb))
    try:
        to_crypto_key(key)
    except ValueError as exc:
        raise InvalidKeyError("clé publique : point hors de la courbe P-256") from exc
    return key


def verify_es256(key: PublicKey, message: bytes, signature: bytes) -> bool:
    """Vrai si ``signature`` (r‖s, 64 octets) signe ``message`` pour ``key``."""
    if len(signature) != 2 * _COORD_BYTES:
        return False
    r = int.from_bytes(signature[:_COORD_BYTES])
    s = int.from_bytes(signature[_COORD_BYTES:])
    # Bornes contrôlées avant la bibliothèque (OpenSSL les refuse aussi : défense en profondeur).
    if not (0 < r < N and 0 < s < N):
        return False
    try:
        to_crypto_key(key).verify(encode_dss_signature(r, s), message, _ALGORITHM)
    except (InvalidSignature, ValueError):
        return False
    return True
