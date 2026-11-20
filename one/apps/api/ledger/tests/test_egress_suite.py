"""R9 — la garde d'egress couvre TOUTE la suite, pas seulement le module integrations.

Ce test n'installe aucune garde lui-même : il s'appuie sur la fixture de session de
``apps/api/conftest.py``. Si elle est retirée, la connexion part réellement (délai dépassé sur
une adresse de documentation, ou résolution DNS d'un hôte public) et ce test échoue.
"""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

import pytest

from api.integrations.egress import EgressDeniedError

# Adresse réservée à la documentation (RFC 5737) : jamais routée, aucun risque de sortie réelle.
UNLISTED_IP = "192.0.2.10"


def test_connexion_ip_hors_liste_refusee_depuis_un_autre_module() -> None:
    with pytest.raises(EgressDeniedError):
        socket.create_connection((UNLISTED_IP, 443), timeout=0.5)


def test_resolution_dns_d_un_hote_public_refusee() -> None:
    with pytest.raises(EgressDeniedError):
        socket.getaddrinfo("api.openai.com", 443)


def test_client_http_de_la_bibliotheque_standard_refuse() -> None:
    with pytest.raises(urllib.error.URLError) as caught:
        urllib.request.urlopen("https://api.openai.com/v1/models", timeout=0.5)
    assert isinstance(caught.value.reason, EgressDeniedError)
