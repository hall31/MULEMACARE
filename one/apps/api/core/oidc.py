"""Fournisseur d'identité OIDC (L10, PRD §10 « fournisseur d'identité ») : jeton d'accès JWT
signé par l'émetteur configuré, vérifié avec ses clés publiques (JWKS).

Vérification (PyJWT, aucune cryptographie maison) :
- en-tête : ``alg`` dans la liste fermée de la configuration (``RS256``, ``ES256`` ; jamais
  ``none`` ni HMAC, donc pas de confusion de clé publique utilisée comme secret HS256) et
  ``kid`` présent ; la clé du JWKS désignée par ``kid`` doit être de la famille de ``alg``
  (RSA pour RS256, EC P-256 pour ES256) et, si elle porte ``alg``, le même ;
- signature, émetteur (``iss``), audience (``aud``), expiration (``exp``), « pas avant »
  (``nbf``) et émission (``iat``) avec une tolérance d'horloge bornée ; ``exp``, ``iat``,
  ``iss``, ``aud`` et ``sub`` sont obligatoires ;
- identité One : ``sub`` → ``users.idp_subject`` et la revendication d'organisation
  (``mulema_org`` par défaut, UUID) → ``users.organization_id`` (Q-L10-01). Le rôle reste lu
  en base (``user_roles``) par ``PrincipalRepository`` : un jeton valide d'un sujet inconnu
  dans cette organisation donne AUTH-01.

JWKS : depuis un fichier local monté (``FileJwksSource``) ou une URL de la liste blanche
d'egress (``HttpJwksSource`` + ``GuardedHttpTransport`` : aucun autre hôte n'est joint).
Rotation : JWKS en cache ``cache_ttl_seconds`` ; un ``kid`` inconnu force UNE relecture, au
plus toutes les ``min_refresh_seconds`` (un flot de ``kid`` inventés ne fait pas tomber l'IdP).
Une clé retirée du JWKS cesse d'être acceptée au plus tard à l'expiration du cache.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol
from uuid import UUID

import jwt
from jwt import PyJWK

from api.core.errors import NotAuthenticatedError
from api.core.identity import Identity
from api.core.jsonlog import LOGGER_NAME, log_event
from api.integrations.transport import HttpRequest, HttpTransport

logger = logging.getLogger(f"{LOGGER_NAME}.identity")

SUPPORTED_ALGORITHMS: Final = frozenset({"RS256", "ES256"})
DEFAULT_ORGANIZATION_CLAIM: Final = "mulema_org"
DEFAULT_LEEWAY_SECONDS: Final = 60
MAX_LEEWAY_SECONDS: Final = 300
MAX_TOKEN_BYTES: Final = 8192
MAX_JWKS_BYTES: Final = 65536
MAX_SUBJECT_CHARS: Final = 255
DEFAULT_CACHE_TTL_SECONDS: Final = 600.0
DEFAULT_MIN_REFRESH_SECONDS: Final = 30.0
HTTP_OK: Final = 200
_REQUIRED_CLAIMS: Final = ["exp", "iat", "iss", "aud", "sub"]
_KEY_TYPES: Final = frozenset({"RSA", "EC"})  # jamais « oct » (secret partagé)


class JwksUnavailableError(RuntimeError):
    """JWKS illisible ou injoignable (jamais une raison d'accepter un jeton)."""


@dataclass(frozen=True, slots=True)
class OidcConfig:
    issuer: str
    audience: str
    algorithms: frozenset[str] = SUPPORTED_ALGORITHMS
    organization_claim: str = DEFAULT_ORGANIZATION_CLAIM
    leeway_seconds: int = DEFAULT_LEEWAY_SECONDS

    def __post_init__(self) -> None:
        if not self.issuer or not self.audience:
            msg = "émetteur et audience OIDC obligatoires"
            raise ValueError(msg)
        if not self.algorithms or not self.algorithms <= SUPPORTED_ALGORITHMS:
            msg = f"algorithmes OIDC admis : {sorted(SUPPORTED_ALGORITHMS)} (sous-ensemble)"
            raise ValueError(msg)
        if not 0 <= self.leeway_seconds <= MAX_LEEWAY_SECONDS:
            msg = f"tolérance d'horloge OIDC hors bornes (0 à {MAX_LEEWAY_SECONDS} s)"
            raise ValueError(msg)
        if not self.organization_claim:
            msg = "revendication d'organisation OIDC vide"
            raise ValueError(msg)


class JwksSource(Protocol):
    """Fournit le document JWKS brut (``{"keys": [...]}``)."""

    async def fetch(self) -> Mapping[str, Any]: ...


def _parse_jwks(raw: bytes) -> Mapping[str, Any]:
    if len(raw) > MAX_JWKS_BYTES:
        msg = "JWKS trop volumineux"
        raise JwksUnavailableError(msg)
    try:
        document = json.loads(raw)
    except ValueError as exc:
        msg = "JWKS illisible (JSON attendu)"
        raise JwksUnavailableError(msg) from exc
    if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
        msg = "JWKS sans liste « keys »"
        raise JwksUnavailableError(msg)
    return document


@dataclass(frozen=True, slots=True)
class FileJwksSource:
    """JWKS lu dans un fichier monté (relu à chaque rafraîchissement : rotation par fichier)."""

    path: Path

    async def fetch(self) -> Mapping[str, Any]:
        try:
            raw = await asyncio.to_thread(self.path.read_bytes)
        except OSError as exc:
            msg = "fichier JWKS illisible"
            raise JwksUnavailableError(msg) from exc
        return _parse_jwks(raw)


@dataclass(frozen=True, slots=True)
class HttpJwksSource:
    """JWKS joint par le transport gardé : l'hôte doit être dans la liste blanche (R9)."""

    url: str
    transport: HttpTransport

    async def fetch(self) -> Mapping[str, Any]:
        response = await self.transport.send(
            HttpRequest("GET", self.url, headers={"Accept": "application/json"})
        )
        if response.status != HTTP_OK:
            msg = f"JWKS : statut HTTP {response.status}"
            raise JwksUnavailableError(msg)
        return _parse_jwks(response.body)


def _signing_keys(document: Mapping[str, Any]) -> dict[str, PyJWK]:
    """Clés de signature utilisables, indexées par ``kid`` ; les autres sont ignorées."""
    keys: dict[str, PyJWK] = {}
    for entry in document.get("keys", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("kid"), str):
            continue
        if entry.get("kty") not in _KEY_TYPES or entry.get("use", "sig") != "sig":
            continue
        if "d" in entry:  # clé privée publiée par erreur : ignorée, jamais utilisée
            continue
        try:
            keys[entry["kid"]] = PyJWK(entry)
        except jwt.PyJWTError:
            continue
    return keys


class TokenRejectedError(NotAuthenticatedError):
    """Jeton refusé ; ``reason`` est journalisée (jamais le jeton ni ses revendications)."""

    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason


class OidcIdentityProvider:
    """Implémentation OIDC de ``IdentityProvider`` (``api.core.identity``)."""

    def __init__(
        self,
        config: OidcConfig,
        source: JwksSource,
        *,
        cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        min_refresh_seconds: float = DEFAULT_MIN_REFRESH_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._source = source
        self._ttl = cache_ttl_seconds
        self._min_refresh = min_refresh_seconds
        self._monotonic = monotonic
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at: float | None = None
        self._attempted_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def config(self) -> OidcConfig:
        return self._config

    async def refresh(self) -> None:
        """Relit le JWKS ; en cas d'échec, garde les clés connues (jusqu'à leur expiration)."""
        async with self._lock:
            self._attempted_at = self._monotonic()
            try:
                document = await self._source.fetch()
            except (JwksUnavailableError, OSError):
                log_event(logger, logging.ERROR, "identity.jwks_unavailable")
                if self._expired():
                    self._keys = {}  # JWKS périmé et non relu : plus aucune clé admise
                return
            self._keys = _signing_keys(document)
            self._fetched_at = self._attempted_at
            log_event(logger, logging.INFO, "identity.jwks_loaded", keys=len(self._keys))

    def _expired(self) -> bool:
        return self._fetched_at is None or self._monotonic() - self._fetched_at >= self._ttl

    def _may_retry(self) -> bool:
        return (
            self._attempted_at is None
            or self._monotonic() - self._attempted_at >= self._min_refresh
        )

    async def _key(self, kid: str) -> PyJWK:
        if self._expired() and self._may_retry():
            await self.refresh()
        if kid not in self._keys and self._may_retry():
            await self.refresh()  # rotation : nouvelle clé publiée par l'émetteur
        if self._expired():
            raise TokenRejectedError("jwks_indisponible")
        key = self._keys.get(kid)
        if key is None:
            raise TokenRejectedError("kid_inconnu")
        return key

    async def authenticate(self, bearer_token: str) -> Identity:
        try:
            return await self._authenticate(bearer_token)
        except TokenRejectedError as exc:
            log_event(logger, logging.INFO, "identity.token_rejected", reason=exc.reason)
            raise

    async def _authenticate(self, token: str) -> Identity:
        if len(token) > MAX_TOKEN_BYTES or not token.isascii():
            raise TokenRejectedError("format")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenRejectedError("format") from exc
        algorithm = header.get("alg")
        if not isinstance(algorithm, str) or algorithm not in self._config.algorithms:
            raise TokenRejectedError("algorithme")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise TokenRejectedError("kid_absent")
        key = await self._key(kid)
        if key.algorithm_name != algorithm:
            raise TokenRejectedError("algorithme_de_cle")
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key.key,
                algorithms=[algorithm],
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=self._config.leeway_seconds,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenRejectedError("expire") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenRejectedError("audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise TokenRejectedError("emetteur") from exc
        except jwt.InvalidSignatureError as exc:
            raise TokenRejectedError("signature") from exc
        except jwt.ImmatureSignatureError as exc:
            raise TokenRejectedError("pas_encore_valide") from exc
        except jwt.PyJWTError as exc:
            raise TokenRejectedError("invalide") from exc
        return self._identity(claims)

    def _identity(self, claims: Mapping[str, Any]) -> Identity:
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > MAX_SUBJECT_CHARS:
            raise TokenRejectedError("sujet")
        organization = claims.get(self._config.organization_claim)
        if not isinstance(organization, str):
            raise TokenRejectedError("organisation")
        try:
            organization_id = UUID(organization)
        except ValueError as exc:
            raise TokenRejectedError("organisation") from exc
        return Identity(subject=subject, organization_id=organization_id)
