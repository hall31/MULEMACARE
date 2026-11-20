"""Résidence des données (R9) : liste blanche réseau et garde d'egress.

Deux barrières indépendantes :

1. ``GuardedHttpTransport`` (module ``http``) refuse un hôte hors liste avant d'ouvrir quoi
   que ce soit ;
2. ``egress_guard`` remplace, le temps d'un bloc, ``socket.getaddrinfo`` et les méthodes de
   connexion de ``socket.socket`` : toute bibliothèque (http.client, urllib, asyncio, un futur
   client HTTP) est refusée hors liste, y compris pendant les tests. La résolution DNS d'un nom
   non listé est elle-même refusée, car elle révèle déjà la destination.

Les gardes s'empilent : chaque bloc ajoute une couche et une connexion doit être admise par
TOUTES les couches actives. Une garde imbriquée ne peut donc que restreindre. Couches en place :
la suite de tests entière (``apps/api/conftest.py``), l'application (``create_app``, lifespan),
et les tests qui veulent une liste plus étroite.

Seules les familles ``AF_INET`` et ``AF_INET6`` sont contrôlées ; les sockets Unix locales
(PostgreSQL de test, boucle asyncio) ne quittent pas la machine. Les pilotes en C (libpq de
psycopg) ouvrent leurs sockets hors du module ``socket`` de Python : la garde ne les voit pas, et
la base est de toute façon une destination listée.

Format de ``infra/egress-allowlist.txt`` : une entrée par ligne, ``<PAYS> <hôte>:<port>``,
commentaires après ``#``. Aucun joker, port obligatoire.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from api.core.jsonlog import LOGGER_NAME, log_event

ONE_ROOT = Path(__file__).resolve().parents[3]
INFRA_DIR = ONE_ROOT / "infra"
ALLOWLIST_PATH = INFRA_DIR / "egress-allowlist.txt"
COUNTRIES = frozenset({"CI", "SN"})
MAX_PORT = 65535

logger = logging.getLogger(f"{LOGGER_NAME}.integrations.egress")


class EgressDeniedError(PermissionError):
    """Connexion refusée : destination absente de la liste blanche.

    Erreur de configuration, jamais une panne passagère : l'API la rend en ``SYS-01`` (code du
    contrat), et elle n'est jamais convertie en ``INT-01``. Hérite d'``OSError`` pour que toute
    bibliothèque réseau la traite comme un échec de connexion, jamais comme un succès partiel.
    """

    code = "SYS-01"

    def __init__(self, host: str, port: int | None) -> None:
        self.host = host
        self.port = port
        where = host if port is None else f"{host}:{port}"
        super().__init__(f"egress refusé : destination hors liste blanche ({where})")


@dataclass(frozen=True, slots=True)
class Endpoint:
    """Destination autorisée : hôte (minuscules) et port exacts."""

    host: str
    port: int

    @classmethod
    def parse(cls, raw: str) -> Endpoint:
        host, sep, port_text = raw.strip().rpartition(":")
        if not sep or not host or not port_text.isdigit():
            raise ValueError(f"entrée sans port explicite : {raw!r}")
        port = int(port_text)
        if not 0 < port <= MAX_PORT:
            raise ValueError(f"port invalide : {raw!r}")
        return cls(host.strip("[]").lower(), port)

    def __str__(self) -> str:
        return f"{self.host}:{self.port}"


def is_loopback(host: str) -> bool:
    """``localhost`` ou adresse de boucle locale (127.0.0.0/8, ::1)."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True, slots=True)
class EgressAllowlist:
    """Ensemble fermé des destinations autorisées pour une instance.

    ``loopback`` : admet toute destination de boucle locale (elle ne quitte pas la machine).
    Réservé à la garde de la suite de tests (serveurs simulés sur ports éphémères) ; jamais
    positionné par ``load_allowlist``, donc jamais en production.
    """

    endpoints: frozenset[Endpoint]
    loopback: bool = False

    def allows(self, host: str, port: int) -> bool:
        wanted = host.strip("[]").lower()
        return Endpoint(wanted, port) in self.endpoints or (self.loopback and is_loopback(wanted))

    def allows_host(self, host: str) -> bool:
        wanted = host.strip("[]").lower()
        return any(e.host == wanted for e in self.endpoints) or (
            self.loopback and is_loopback(wanted)
        )

    def check(self, host: str, port: int) -> None:
        if not self.allows(host, port):
            log_event(logger, logging.WARNING, "egress.denied", host=host, port=port)
            raise EgressDeniedError(host, port)


def load_allowlist(path: Path, *, country: str) -> EgressAllowlist:
    """Charge les entrées d'un pays. Toute ligne mal formée fait échouer le chargement."""
    if country not in COUNTRIES:
        raise ValueError(f"pays inconnu : {country!r} (attendu : {sorted(COUNTRIES)})")
    endpoints: set[Endpoint] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        content = line.split("#", 1)[0].strip()
        if not content:
            continue
        parts = content.split()
        if len(parts) != 2:  # noqa: PLR2004 — format « PAYS hôte:port »
            raise ValueError(f"{path.name}:{number} : attendu « PAYS hôte:port », lu {line!r}")
        line_country, raw = parts
        if line_country not in COUNTRIES:
            raise ValueError(f"{path.name}:{number} : pays inconnu {line_country!r}")
        if "*" in raw:
            raise ValueError(f"{path.name}:{number} : joker interdit")
        if line_country == country:
            endpoints.add(Endpoint.parse(raw))
    return EgressAllowlist(frozenset(endpoints))


# --- Garde au niveau socket --------------------------------------------------------------------

_INET = (socket.AF_INET, socket.AF_INET6)


@dataclass(eq=False, slots=True)
class _Layer:
    """Une garde active : sa liste et les adresses obtenues en résolvant un hôte listé."""

    allowlist: EgressAllowlist
    resolved: set[tuple[str, int]] = field(default_factory=set)

    def admits(self, ip: str, port: int) -> bool:
        return (ip, port) in self.resolved or self.allowlist.allows(ip, port)


_lock = threading.Lock()
_layers: list[_Layer] = []
_saved: dict[str, Any] = {}


def _active() -> tuple[_Layer, ...]:
    with _lock:
        return tuple(_layers)


def _port_of(port: object) -> int | None:
    if port is None:
        return None
    if isinstance(port, int):
        return port
    if isinstance(port, (str, bytes)):
        text = port.decode() if isinstance(port, bytes) else port
        if text.isdigit():
            return int(text)
        return socket.getservbyname(text)
    return None


def _guarded_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    name = host.decode() if isinstance(host, bytes) else str(host)
    wanted = _port_of(port)
    layers = _active()
    for layer in layers:
        allowlist = layer.allowlist
        allowed = (
            allowlist.allows(name, wanted) if wanted is not None else allowlist.allows_host(name)
        )
        if not allowed:
            log_event(logger, logging.WARNING, "egress.denied_dns", host=name, port=wanted)
            raise EgressDeniedError(name, wanted)
    infos = _saved["getaddrinfo"](host, port, *args, **kwargs)
    for info in infos:
        address = (str(info[4][0]).lower(), int(info[4][1]))
        for layer in layers:
            layer.resolved.add(address)
    return infos


def _check_address(sock: socket.socket, address: Any) -> None:  # noqa: ANN401
    if sock.family not in _INET:
        return
    ip, port = str(address[0]).lower(), int(address[1])
    if all(layer.admits(ip, port) for layer in _active()):
        return
    log_event(logger, logging.WARNING, "egress.denied", host=ip, port=port)
    raise EgressDeniedError(ip, port)


def _guarded_connect(self: socket.socket, address: Any) -> None:  # noqa: ANN401
    _check_address(self, address)
    _saved["connect"](self, address)


def _guarded_connect_ex(self: socket.socket, address: Any) -> int:  # noqa: ANN401
    _check_address(self, address)
    result: int = _saved["connect_ex"](self, address)
    return result


def _guarded_sendto(self: socket.socket, data: Any, *args: Any) -> int:  # noqa: ANN401
    _check_address(self, args[-1])
    sent: int = _saved["sendto"](self, data, *args)
    return sent


_REPLACEMENTS: dict[str, Callable[..., Any]] = {
    "connect": _guarded_connect,
    "connect_ex": _guarded_connect_ex,
    "sendto": _guarded_sendto,
}


def _install() -> None:
    _saved["getaddrinfo"] = socket.getaddrinfo
    for name in _REPLACEMENTS:
        _saved[name] = getattr(socket.socket, name)
    socket.getaddrinfo = _guarded_getaddrinfo
    for name, func in _REPLACEMENTS.items():
        setattr(socket.socket, name, func)


def _uninstall() -> None:
    socket.getaddrinfo = _saved.pop("getaddrinfo")
    for name in _REPLACEMENTS:
        setattr(socket.socket, name, _saved.pop(name))


@contextmanager
def egress_guard(allowlist: EgressAllowlist) -> Iterator[None]:
    """Refuse toute connexion IP hors liste blanche pendant le bloc.

    Empilable : la couche ajoutée restreint les couches déjà actives, sans jamais les élargir.
    Une adresse IP est admise par une couche si elle figure littéralement dans sa liste, ou si
    elle a été obtenue par la résolution d'un hôte admis, sur le même port, pendant la couche.
    Le module ``socket`` est restauré à la sortie de la dernière couche.
    """
    layer = _Layer(allowlist)
    with _lock:
        if not _layers:
            _install()
        _layers.append(layer)
    try:
        yield
    finally:
        with _lock:
            _layers.remove(layer)  # par identité : l'ordre de sortie peut varier (threads)
            if not _layers:
                _uninstall()
