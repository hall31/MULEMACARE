"""Limitation de débit (L10, CR-L10-01) : par adresse IP et par jeton, avant toute logique.

Opérations limitées (``DEFAULT_RULES``) : lectures publiques (marque par identifiant public,
page et paiement d'un lien public), webhooks de paiement, mesure produit
(``recordProductEvent``, Q-P2-07) et tentatives d'identification au comptoir. Une demande
refusée reçoit un 429 ``RATE-01`` (problem+json, ``retry_after_seconds`` et en-tête
``Retry-After``), AVANT l'authentification et avant la base : une rafale de jetons faux ou de
signatures fausses est freinée sans coûter une transaction.

Clés :
- IP : adresse du pair TCP ; derrière un mandataire inverse, seulement si ce pair est dans
  ``trusted_proxies`` : on remonte alors ``X-Forwarded-For`` de droite à gauche jusqu'à la
  première adresse non fiable (un client ne peut pas choisir sa propre clé) ;
- jeton : empreinte SHA-256 du jeton porteur (jamais le jeton lui-même, ni en mémoire ni dans
  un journal). Un jeton absent n'a pas de seau « jeton », la limite IP s'applique toujours.

Algorithme : seau à jetons (capacité = ``requests``, remplissage continu sur ``per_seconds``).
Stockage : ``InMemoryRateLimitStore`` par défaut (un processus) ; ``RateLimitStore`` est
l'interface d'un stockage partagé (Redis, plusieurs instances), non fourni (Q-L10-03).
Seuils : défauts à valider (specs/QUESTIONS.md, Q-L10-02).
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import math
import re
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol

from fastapi.routing import iter_route_contexts
from starlette.routing import BaseRoute
from starlette.types import ASGIApp, Receive, Scope, Send

from api.core.errors import RateLimitedError
from api.core.jsonlog import LOGGER_NAME, log_event

logger = logging.getLogger(f"{LOGGER_NAME}.ratelimit")

type IpNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network
type Dimension = Literal["ip", "jeton"]

DEFAULT_MAX_KEYS: Final = 100_000
_MINUTE: Final = 60.0


@dataclass(frozen=True, slots=True)
class Limit:
    """``requests`` demandes par fenêtre glissante de ``per_seconds`` secondes."""

    requests: int
    per_seconds: float = _MINUTE

    def __post_init__(self) -> None:
        if self.requests < 1 or self.per_seconds <= 0:
            msg = "limite de débit invalide (au moins 1 demande sur une durée positive)"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class RateRule:
    per_ip: Limit | None = None
    per_token: Limit | None = None


# Défauts à valider (Q-L10-02) : un comptoir partage souvent une IP (NAT de la clinique), d'où
# une limite IP plus large que la limite par jeton.
DEFAULT_RULES: Final[Mapping[str, RateRule]] = {
    "getOrganizationBranding": RateRule(per_ip=Limit(60)),
    "getPublicPaymentLink": RateRule(per_ip=Limit(30)),
    "startCheckout": RateRule(per_ip=Limit(10)),
    "receivePaymentWebhook": RateRule(per_ip=Limit(300)),
    "recordProductEvent": RateRule(per_ip=Limit(600), per_token=Limit(120)),
    "startIdentification": RateRule(per_ip=Limit(60), per_token=Limit(20)),
    "sendIdentificationCode": RateRule(per_ip=Limit(30), per_token=Limit(10)),
    "verifyIdentificationCode": RateRule(per_ip=Limit(60), per_token=Limit(20)),
}


class RateLimitStore(Protocol):
    """Prend un jeton dans le seau ``key`` : 0 si admis, sinon secondes avant le prochain."""

    async def acquire(self, key: str, limit: Limit) -> float: ...


class InMemoryRateLimitStore:
    """Seaux en mémoire du processus, bornés à ``max_keys`` (le moins récent est évincé).

    Aucune attente (``await``) entre lecture et écriture : sur une boucle asyncio, ``acquire``
    est atomique sans verrou."""

    def __init__(
        self, *, max_keys: int = DEFAULT_MAX_KEYS, now: Callable[[], float] = time.monotonic
    ) -> None:
        self._max_keys = max_keys
        self._now = now
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._buckets)

    async def acquire(self, key: str, limit: Limit) -> float:
        now = self._now()
        rate = limit.requests / limit.per_seconds
        tokens, updated = self._buckets.pop(key, (float(limit.requests), now))
        tokens = min(float(limit.requests), tokens + (now - updated) * rate)
        if tokens >= 1.0:
            tokens -= 1.0
            wait = 0.0
        else:
            wait = (1.0 - tokens) / rate
        self._buckets[key] = (tokens, now)
        while len(self._buckets) > self._max_keys:
            self._buckets.popitem(last=False)
        return wait


def parse_trusted_proxies(raw: str) -> tuple[IpNetwork, ...]:
    """``MULEMA_TRUSTED_PROXIES`` : adresses ou réseaux séparés par des virgules."""
    return tuple(ipaddress.ip_network(p.strip(), strict=False) for p in raw.split(",") if p.strip())


def _ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def client_ip(scope: Scope, trusted: Sequence[IpNetwork]) -> str:
    """Adresse du client : le pair TCP, ou la première adresse non fiable de
    ``X-Forwarded-For`` (lue de droite à gauche) si le pair est un mandataire de confiance."""
    client = scope.get("client")
    peer = str(client[0]) if client else "inconnu"
    current = _ip(peer)
    if current is None or not any(current in net for net in trusted):
        return peer
    forwarded = [
        value.decode("latin-1")
        for name, value in scope.get("headers", [])
        if name == b"x-forwarded-for"
    ]
    hops = [hop for line in forwarded for hop in line.split(",")]
    for hop in reversed(hops):
        address = _ip(hop)
        if address is None:
            break  # entrée illisible : on s'arrête au dernier saut vérifié
        current = address
        if not any(address in net for net in trusted):
            break
    return str(current)


def token_fingerprint(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            scheme, _, token = value.decode("latin-1").partition(" ")
            if scheme.lower() == "bearer" and token.strip():
                return hashlib.sha256(token.strip().encode()).hexdigest()[:32]
            return None
    return None


@dataclass(frozen=True, slots=True)
class RateLimits:
    """Configuration de l'application : règles par ``operationId``, stockage, mandataires."""

    rules: Mapping[str, RateRule] = field(default_factory=lambda: dict(DEFAULT_RULES))
    store: RateLimitStore = field(default_factory=InMemoryRateLimitStore)
    trusted_proxies: tuple[IpNetwork, ...] = ()


@dataclass(frozen=True, slots=True)
class _Target:
    """Route limitée telle que servie (préfixes des routeurs inclus résolus par FastAPI)."""

    route: BaseRoute
    path_regex: re.Pattern[str]
    methods: frozenset[str]
    operation: str
    rule: RateRule

    def matches(self, scope: Scope) -> bool:
        path = str(scope.get("path", ""))
        root = str(scope.get("root_path", ""))
        if root and path.startswith(root):
            path = path[len(root) :]
        return scope.get("method") in self.methods and self.path_regex.match(path) is not None


def _limited_routes(
    routes: Sequence[BaseRoute], rules: Mapping[str, RateRule]
) -> tuple[_Target, ...]:
    found: list[_Target] = []
    for context in iter_route_contexts(routes):
        operation = getattr(context, "operation_id", None)
        regex = getattr(context, "path_regex", None)
        if operation in rules and isinstance(regex, re.Pattern):
            found.append(
                _Target(
                    route=context.original_route,
                    path_regex=regex,
                    methods=frozenset(context.methods or ()),
                    operation=str(operation),
                    rule=rules[str(operation)],
                )
            )
    return tuple(found)


def missing_operations(routes: Sequence[BaseRoute], rules: Mapping[str, RateRule]) -> list[str]:
    """Règles sans route montée (opération renommée ou retirée) : la limite ne s'appliquerait
    plus en silence. ``create_app`` refuse alors de construire l'application assemblée."""
    mounted = {target.operation for target in _limited_routes(routes, rules)}
    return sorted(set(rules) - mounted)


class RateLimitMiddleware:
    """Middleware ASGI : identifie l'opération limitée, débite les seaux IP et jeton."""

    def __init__(
        self, app: ASGIApp, *, routes: Callable[[], Sequence[BaseRoute]], limits: RateLimits
    ) -> None:
        self._app = app
        self._routes = routes
        self._limits = limits
        self._targets: tuple[_Target, ...] | None = None

    def _match(self, scope: Scope) -> _Target | None:
        if self._targets is None:  # routes complètes au premier appel (après tous les montages)
            self._targets = _limited_routes(self._routes(), self._limits.rules)
        return next((t for t in self._targets if t.matches(scope)), None)

    async def _wait(self, operation: str, rule: RateRule, scope: Scope) -> tuple[float, Dimension]:
        store = self._limits.store
        if rule.per_ip is not None:
            ip = client_ip(scope, self._limits.trusted_proxies)
            wait = await store.acquire(f"{operation}:ip:{ip}", rule.per_ip)
            if wait > 0:
                return wait, "ip"
        if rule.per_token is not None and (fingerprint := token_fingerprint(scope)):
            wait = await store.acquire(f"{operation}:jeton:{fingerprint}", rule.per_token)
            if wait > 0:
                return wait, "jeton"
        return 0.0, "ip"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or (target := self._match(scope)) is None:
            await self._app(scope, receive, send)
            return
        route, operation = target.route, target.operation
        wait, dimension = await self._wait(operation, target.rule, scope)
        if wait <= 0:
            await self._app(scope, receive, send)
            return
        scope["route"] = route  # journal d'accès : route connue, même refusée
        log_event(
            logger, logging.WARNING, "ratelimit.refused", operation=operation, dimension=dimension
        )
        # Import local : api.core.app importe ce module (rendu problem+json partagé).
        from api.core.app import problem_response  # noqa: PLC0415

        state = scope.get("state") or {}
        request_id = state.get("request_id") if isinstance(state, dict) else None
        error = RateLimitedError(math.ceil(wait))
        response = problem_response(
            error, request_id if isinstance(request_id, str) else "req_inconnu"
        )
        response.headers["Retry-After"] = str(error.retry_after_seconds)
        await response(scope, receive, send)
