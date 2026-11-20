"""Émetteur OIDC FICTIF pour les tests : clés générées à chaque exécution (aucune clé dans le
dépôt), JWKS public et jetons signés par PyJWT."""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

ISSUER = "https://idp.mulemacare.invalid/realms/one"
AUDIENCE = "mulemacare-one-api"

type PrivateKey = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey


@dataclass
class SigningKey:
    kid: str
    algorithm: str
    private: PrivateKey

    def public_jwk(self) -> dict[str, Any]:
        public = self.private.public_key()
        if isinstance(public, rsa.RSAPublicKey):
            jwk: dict[str, Any] = RSAAlgorithm.to_jwk(public, as_dict=True)
        else:
            jwk = ECAlgorithm.to_jwk(public, as_dict=True)
        return jwk | {"kid": self.kid, "use": "sig", "alg": self.algorithm}


def rsa_key(kid: str | None = None) -> SigningKey:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return SigningKey(kid or f"rsa-{uuid.uuid4().hex[:8]}", "RS256", private)


def ec_key(kid: str | None = None) -> SigningKey:
    private = ec.generate_private_key(ec.SECP256R1())
    return SigningKey(kid or f"ec-{uuid.uuid4().hex[:8]}", "ES256", private)


def claims(
    subject: str, organization_id: uuid.UUID, *, lifetime: int = 300, **extra: object
) -> dict[str, Any]:
    now = int(time.time())
    base: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": subject,
        "iat": now,
        "exp": now + lifetime,
        "mulema_org": str(organization_id),
    }
    return base | extra


def sign(
    key: SigningKey, payload: Mapping[str, Any], *, headers: Mapping[str, Any] | None = None
) -> str:
    return jwt.encode(
        dict(payload),
        key.private,
        algorithm=key.algorithm,
        headers={"kid": key.kid} | dict(headers or {}),
    )


@dataclass
class StaticJwks:
    """Source JWKS en mémoire : compte les lectures, simule une panne ou une rotation."""

    keys: list[SigningKey] = field(default_factory=list)
    fetches: int = 0
    failing: bool = False

    async def fetch(self) -> Mapping[str, Any]:
        from api.core.oidc import JwksUnavailableError  # noqa: PLC0415

        self.fetches += 1
        if self.failing:
            msg = "panne simulée"
            raise JwksUnavailableError(msg)
        return {"keys": [k.public_jwk() for k in self.keys]}


class FakeMonotonic:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value
