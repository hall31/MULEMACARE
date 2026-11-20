"""R9 — test réseau `make egress` : aucune requête ne sort hors de la liste blanche.

Chaque test démarre un vrai serveur local qui compte les requêtes reçues. Un hôte hors liste
doit être refusé AVANT toute connexion : si la garde est retirée ou affaiblie, le serveur
reçoit la requête et le test échoue.
"""

from __future__ import annotations

import asyncio
import http.client
import io
import json
import logging
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from api.core.jsonlog import LOGGER_NAME, JsonFormatter
from api.integrations.egress import (
    ALLOWLIST_PATH,
    EgressAllowlist,
    EgressDeniedError,
    Endpoint,
    egress_guard,
    load_allowlist,
)
from api.integrations.healthos_sim import SimulatedHealthOS
from api.integrations.transport import GuardedHttpTransport, HttpRequest


@pytest.fixture
def listed() -> Iterator[SimulatedHealthOS]:
    """Serveur dont l'adresse est dans la liste blanche du test."""
    with SimulatedHealthOS() as sim:
        yield sim


@pytest.fixture
def unlisted() -> Iterator[SimulatedHealthOS]:
    """Serveur joignable, mais absent de la liste blanche : il ne doit rien recevoir."""
    with SimulatedHealthOS() as sim:
        yield sim


@pytest.fixture
def allowlist(listed: SimulatedHealthOS) -> EgressAllowlist:
    return EgressAllowlist(frozenset({Endpoint("127.0.0.1", listed.port)}))


# --- Fichier infra/egress-allowlist.txt -------------------------------------------------------


def test_allowlist_file_exists_and_parses_for_each_country() -> None:
    for country in ("CI", "SN"):
        allowlist = load_allowlist(ALLOWLIST_PATH, country=country)
        assert allowlist.endpoints, f"liste blanche vide pour {country}"


def test_allowlist_has_no_wildcard_no_public_ai_and_no_foreign_country() -> None:
    text = ALLOWLIST_PATH.read_text(encoding="utf-8")
    forbidden = ("*", "openai", "anthropic", "googleapis", "gstatic", "mistral", "huggingface")
    for line in text.splitlines():
        entry = line.split("#", 1)[0].strip().lower()
        if not entry:
            continue
        assert not any(word in entry for word in forbidden), line
        assert entry.split()[0] in {"ci", "sn"}, f"pays inconnu : {line}"


def test_country_lists_are_disjoint() -> None:
    ci = load_allowlist(ALLOWLIST_PATH, country="CI").endpoints
    sn = load_allowlist(ALLOWLIST_PATH, country="SN").endpoints
    assert not ci & sn, "une instance d'un pays ne doit joindre aucun service de l'autre"


def test_allowlist_parser_rejects_entries_without_port(tmp_path: Path) -> None:
    bad = tmp_path / "allow.txt"
    bad.write_text("CI healthos.ci.example\n", encoding="utf-8")
    with pytest.raises(ValueError, match="port"):
        load_allowlist(bad, country="CI")


def test_allowlist_parser_rejects_unknown_country() -> None:
    with pytest.raises(ValueError, match="pays"):
        load_allowlist(ALLOWLIST_PATH, country="FR")


# --- Garde au niveau socket (couvre toute bibliothèque) --------------------------------------


def test_guard_blocks_raw_socket_to_unlisted_port(
    allowlist: EgressAllowlist, unlisted: SimulatedHealthOS
) -> None:
    with egress_guard(allowlist), pytest.raises(EgressDeniedError):
        socket.create_connection(("127.0.0.1", unlisted.port), timeout=2)
    assert unlisted.requests == []


def test_guard_blocks_http_client_and_urllib(
    allowlist: EgressAllowlist, unlisted: SimulatedHealthOS
) -> None:
    url = f"http://127.0.0.1:{unlisted.port}/api/v1/fhir/R4/metadata"
    with egress_guard(allowlist):
        conn = http.client.HTTPConnection("127.0.0.1", unlisted.port, timeout=2)
        with pytest.raises(EgressDeniedError):
            conn.request("GET", "/api/v1/fhir/R4/metadata")
        with pytest.raises(urllib.error.URLError) as caught:
            urllib.request.urlopen(url, timeout=2)
        assert isinstance(caught.value.reason, EgressDeniedError)
    assert unlisted.requests == []


def test_guard_blocks_direct_ip_connect_without_resolution(
    allowlist: EgressAllowlist, unlisted: SimulatedHealthOS
) -> None:
    # socket.connect sur une IP littérale ne passe pas par getaddrinfo : contrôle distinct.
    with egress_guard(allowlist), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        with pytest.raises(EgressDeniedError):
            sock.connect(("127.0.0.1", unlisted.port))
        with pytest.raises(EgressDeniedError):
            sock.connect_ex(("127.0.0.1", unlisted.port))
    assert unlisted.requests == []


def test_guard_blocks_udp_sendto(allowlist: EgressAllowlist) -> None:
    # Un DNS « maison » ou tout envoi UDP hors liste est refusé.
    with (
        egress_guard(allowlist),
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock,
        pytest.raises(EgressDeniedError),
    ):
        sock.sendto(b"x", ("192.0.2.53", 53))


def test_guard_blocks_dns_resolution_of_unlisted_host(allowlist: EgressAllowlist) -> None:
    # Résoudre un nom révèle déjà l'intention : la résolution elle-même est refusée.
    with egress_guard(allowlist), pytest.raises(EgressDeniedError):
        socket.getaddrinfo("api.openai.com", 443)


def test_guard_blocks_asyncio_connections(
    allowlist: EgressAllowlist, unlisted: SimulatedHealthOS
) -> None:
    async def attempt() -> None:
        await asyncio.open_connection("127.0.0.1", unlisted.port)

    with egress_guard(allowlist), pytest.raises(EgressDeniedError):
        asyncio.run(attempt())
    assert unlisted.requests == []


def test_guard_lets_listed_endpoint_through(
    allowlist: EgressAllowlist, listed: SimulatedHealthOS
) -> None:
    with egress_guard(allowlist):
        conn = http.client.HTTPConnection("127.0.0.1", listed.port, timeout=2)
        conn.request("GET", "/api/v1/fhir/R4/metadata")
        assert conn.getresponse().status == http.HTTPStatus.OK
        conn.close()
    assert len(listed.requests) == 1


def test_inner_guard_is_removed_on_exit(
    allowlist: EgressAllowlist, unlisted: SimulatedHealthOS
) -> None:
    # La garde de session (conftest) admet la boucle locale ; la garde interne la restreint.
    with egress_guard(allowlist), pytest.raises(EgressDeniedError):
        socket.create_connection(("127.0.0.1", unlisted.port), timeout=2).close()
    socket.create_connection(("127.0.0.1", unlisted.port), timeout=2).close()


def test_nested_guard_only_narrows(listed: SimulatedHealthOS, unlisted: SimulatedHealthOS) -> None:
    only_listed = EgressAllowlist(frozenset({Endpoint("127.0.0.1", listed.port)}))
    both = EgressAllowlist(
        frozenset({Endpoint("127.0.0.1", listed.port), Endpoint("127.0.0.1", unlisted.port)})
    )
    # Une garde imbriquée plus large n'ouvre rien que la garde englobante refuse.
    with egress_guard(only_listed), egress_guard(both), pytest.raises(EgressDeniedError):
        socket.create_connection(("127.0.0.1", unlisted.port), timeout=2)
    assert unlisted.requests == []


def test_last_guard_restores_the_socket_module() -> None:
    # Processus neuf : aucune garde de session, on vérifie la restauration complète.
    code = (
        "import socket\n"
        "from api.integrations.egress import EgressAllowlist, egress_guard\n"
        "before = (socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex,"
        " socket.socket.sendto)\n"
        "with egress_guard(EgressAllowlist(frozenset())):\n"
        "    assert socket.socket.connect is not before[1]\n"
        "after = (socket.getaddrinfo, socket.socket.connect, socket.socket.connect_ex,"
        " socket.socket.sendto)\n"
        "assert all(a is b for a, b in zip(before, after, strict=True))\n"
    )
    apps_dir = Path(__file__).resolve().parents[3]
    env = {**os.environ, "PYTHONPATH": str(apps_dir)}
    result = subprocess.run(  # noqa: S603 — interpréteur courant, code constant
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_denial_is_logged_as_json_without_payload() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with pytest.raises(EgressDeniedError):
            socket.getaddrinfo("api.openai.com", 443)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]
    denied = [line for line in lines if line["event"] == "egress.denied_dns"]
    assert denied, lines
    assert denied[0]["logger"] == f"{LOGGER_NAME}.integrations.egress"
    assert denied[0]["host"] == "api.openai.com"
    assert denied[0]["port"] == 443


# --- Transport HTTP du client (refus avant toute connexion) -----------------------------------


def test_transport_refuses_unlisted_host_even_without_socket_guard(
    allowlist: EgressAllowlist, unlisted: SimulatedHealthOS
) -> None:
    transport = GuardedHttpTransport(allowlist, timeout_seconds=2)
    request = HttpRequest("GET", f"http://127.0.0.1:{unlisted.port}/api/v1/fhir/R4/metadata")
    with pytest.raises(EgressDeniedError):
        asyncio.run(transport.send(request))
    assert unlisted.requests == []


def test_transport_refuses_public_host_by_name(allowlist: EgressAllowlist) -> None:
    transport = GuardedHttpTransport(allowlist, timeout_seconds=2)
    with pytest.raises(EgressDeniedError):
        asyncio.run(transport.send(HttpRequest("GET", "https://api.openai.com/v1/models")))


def test_transport_reaches_listed_host(
    allowlist: EgressAllowlist, listed: SimulatedHealthOS
) -> None:
    transport = GuardedHttpTransport(allowlist, timeout_seconds=2)
    request = HttpRequest("GET", f"http://127.0.0.1:{listed.port}/api/v1/fhir/R4/metadata")
    response = asyncio.run(transport.send(request))
    assert response.status == http.HTTPStatus.OK
    assert len(listed.requests) == 1


def test_transport_does_not_follow_redirects_outside_allowlist(
    allowlist: EgressAllowlist, listed: SimulatedHealthOS, unlisted: SimulatedHealthOS
) -> None:
    listed.redirect_to = f"http://127.0.0.1:{unlisted.port}/api/v1/fhir/R4/metadata"
    transport = GuardedHttpTransport(allowlist, timeout_seconds=2)
    request = HttpRequest("GET", f"http://127.0.0.1:{listed.port}/api/v1/fhir/R4/metadata")
    response = asyncio.run(transport.send(request))
    assert response.status == http.HTTPStatus.FOUND
    assert unlisted.requests == []


def test_transport_rejects_non_http_schemes(allowlist: EgressAllowlist) -> None:
    transport = GuardedHttpTransport(allowlist, timeout_seconds=2)
    with pytest.raises(EgressDeniedError):
        asyncio.run(transport.send(HttpRequest("GET", "file:///etc/passwd")))
