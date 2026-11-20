"""Transport HTTP gardé : refuse toute destination hors liste blanche avant de se connecter.

Bibliothèque standard uniquement (``http.client``), exécutée hors de la boucle d'événements via
``asyncio.to_thread`` : l'API reste asynchrone sans ajouter de dépendance. Les redirections ne
sont jamais suivies (une redirection vers un hôte non listé serait une fuite).
"""

from __future__ import annotations

import asyncio
import http.client
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

from api.integrations.egress import EgressAllowlist, EgressDeniedError

DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True, slots=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    """Contrat minimal d'un transport HTTP asynchrone."""

    async def send(self, request: HttpRequest) -> HttpResponse: ...


def split_destination(url: str) -> tuple[str, str, int, str]:
    """Renvoie ``(schéma, hôte, port, chemin+requête)`` ; refuse tout schéma non HTTP."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if scheme not in DEFAULT_PORTS or not host:
        raise EgressDeniedError(host or url, None)
    port = parts.port or DEFAULT_PORTS[scheme]
    target = parts.path or "/"
    if parts.query:
        target = f"{target}?{parts.query}"
    return scheme, host, port, target


class GuardedHttpTransport:
    """Transport HTTP/HTTPS limité à une liste blanche."""

    def __init__(self, allowlist: EgressAllowlist, *, timeout_seconds: float) -> None:
        self._allowlist = allowlist
        self._timeout = timeout_seconds

    @property
    def allowlist(self) -> EgressAllowlist:
        return self._allowlist

    async def send(self, request: HttpRequest) -> HttpResponse:
        scheme, host, port, target = split_destination(request.url)
        self._allowlist.check(host, port)
        return await asyncio.to_thread(self._send_blocking, request, scheme, host, port, target)

    def _send_blocking(
        self, request: HttpRequest, scheme: str, host: str, port: int, target: str
    ) -> HttpResponse:
        conn: http.client.HTTPConnection
        if scheme == "https":
            conn = http.client.HTTPSConnection(host, port, timeout=self._timeout)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=self._timeout)
        try:
            conn.request(request.method, target, body=request.body, headers=dict(request.headers))
            response = conn.getresponse()
            return HttpResponse(
                status=response.status,
                headers={k.lower(): v for k, v in response.getheaders()},
                body=response.read(),
            )
        finally:
            conn.close()
