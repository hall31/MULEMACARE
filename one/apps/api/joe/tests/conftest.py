"""Fixtures du lot L8 : le jeu L5 (organisations A et B, prestataires, un utilisateur par rôle),
une API sous le rôle ``mulema_app`` avec les routes L5 (pour créer de vrais dossiers) et JOE.

Toute la suite tourne déjà sous ``egress_guard`` (apps/api/conftest.py) ; l'application ajoute sa
propre garde (lifespan), limitée au serveur HealthOS simulé.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.claims.tests.conftest import ClaimsSeed, claims_seed, seed  # noqa: F401 — fixtures L5
from api.joe.tests.support import JoeHarness, Scenario, SpyModel, build_client, build_scenario


@pytest.fixture(scope="module")
def harness(claims_seed: ClaimsSeed) -> Iterator[JoeHarness]:  # noqa: F811
    spy = SpyModel()
    with build_client(claims_seed, spy) as client:
        scenario = build_scenario(client, claims_seed)
        yield JoeHarness(client=client, seed=claims_seed, spy=spy, scenario=scenario)


@pytest.fixture
def client(harness: JoeHarness) -> TestClient:
    return harness.client


@pytest.fixture
def scenario(harness: JoeHarness) -> Scenario:
    return harness.scenario
