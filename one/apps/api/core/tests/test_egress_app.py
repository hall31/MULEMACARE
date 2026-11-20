"""R9 — l'application installe la garde d'egress à son démarrage (``create_app``, lifespan).

La liste blanche vient de ``Settings.egress_allowlist`` (production : fichier
``infra/egress-allowlist.txt`` du pays ``MULEMA_COUNTRY``). Par défaut, elle est VIDE : rien ne
sort (échec fermé).
"""

from __future__ import annotations

import socket
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.core.app import create_app
from api.core.identity import InMemoryIdentityProvider
from api.core.settings import Settings
from api.core.tests.conftest import APP_ROLE, CoreSeed
from api.integrations.egress import (
    ALLOWLIST_PATH,
    EgressAllowlist,
    EgressDeniedError,
    Endpoint,
    load_allowlist,
)
from api.integrations.healthos_sim import SimulatedHealthOS


@pytest.fixture
def listed() -> Iterator[SimulatedHealthOS]:
    with SimulatedHealthOS() as sim:
        yield sim


@pytest.fixture
def unlisted() -> Iterator[SimulatedHealthOS]:
    with SimulatedHealthOS() as sim:
        yield sim


def _connect(port: int) -> None:
    socket.create_connection(("127.0.0.1", port), timeout=2).close()


def test_garde_active_pendant_la_vie_de_l_application(
    core_seed: CoreSeed, listed: SimulatedHealthOS, unlisted: SimulatedHealthOS
) -> None:
    allowlist = EgressAllowlist(frozenset({Endpoint("127.0.0.1", listed.port)}))
    app = create_app(
        Settings(database_url=core_seed.url, app_role=APP_ROLE, egress_allowlist=allowlist),
        identity_provider=InMemoryIdentityProvider(),
    )
    with TestClient(app):
        _connect(listed.port)
        with pytest.raises(EgressDeniedError):
            _connect(unlisted.port)
    # Application arrêtée : seule la garde de session des tests reste (boucle locale admise).
    _connect(unlisted.port)


def test_liste_blanche_vide_par_defaut(core_seed: CoreSeed, listed: SimulatedHealthOS) -> None:
    settings = Settings(database_url=core_seed.url, app_role=APP_ROLE)
    assert settings.egress_allowlist.endpoints == frozenset()
    app = create_app(settings, identity_provider=InMemoryIdentityProvider())
    with TestClient(app), pytest.raises(EgressDeniedError):
        _connect(listed.port)


def test_from_env_charge_la_liste_du_pays(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MULEMA_INSURANCE_DATABASE_URL", "postgresql+psycopg://x@/y")
    monkeypatch.setenv("MULEMA_COUNTRY", "SN")
    settings = Settings.from_env()
    assert settings.egress_allowlist == load_allowlist(ALLOWLIST_PATH, country="SN")

    monkeypatch.delenv("MULEMA_COUNTRY")
    with pytest.raises(RuntimeError, match="MULEMA_COUNTRY"):
        Settings.from_env()
