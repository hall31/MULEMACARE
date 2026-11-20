"""R9 — configuration de déploiement par pays (CI, SN) cohérente avec la liste blanche."""

from __future__ import annotations

import asyncio
import tomllib
import uuid
from pathlib import Path

import pytest

from api.integrations.deployment import (
    COUNTRY_TIMEZONES,
    DEPLOY_DIR,
    build_healthos_client,
    load_deployment,
)
from api.integrations.egress import ALLOWLIST_PATH, EgressDeniedError, Endpoint, load_allowlist

COUNTRIES = ("CI", "SN")


@pytest.mark.parametrize("country", COUNTRIES)
def test_each_country_has_a_valid_deployment(country: str) -> None:
    deployment = load_deployment(country)
    assert deployment.country_code == country
    assert deployment.timezone == COUNTRY_TIMEZONES[country]
    assert deployment.currency == "XOF"
    assert deployment.healthos_fhir_base_url.startswith("https://")


@pytest.mark.parametrize("country", COUNTRIES)
def test_declared_endpoints_match_the_allowlist_exactly(country: str) -> None:
    deployment = load_deployment(country)
    allowlist = load_allowlist(ALLOWLIST_PATH, country=country)
    assert deployment.egress_endpoints == allowlist.endpoints
    assert deployment.healthos_endpoint in allowlist.endpoints


def test_an_instance_cannot_reach_the_other_country() -> None:
    ci = load_deployment("CI")
    sn = load_deployment("SN")
    assert ci.healthos_endpoint not in load_allowlist(ALLOWLIST_PATH, country="SN").endpoints
    assert sn.healthos_endpoint not in load_allowlist(ALLOWLIST_PATH, country="CI").endpoints


def test_ci_client_refuses_sn_healthos_before_any_network() -> None:
    sn_url = load_deployment("SN").healthos_fhir_base_url
    ci_client = build_healthos_client(load_deployment("CI"))
    wrong = ci_client.with_base_url(sn_url)
    with pytest.raises(EgressDeniedError):
        asyncio.run(wrong.resolve_patient(uuid.uuid4()))


def test_deployment_rejects_endpoint_missing_from_allowlist(tmp_path: Path) -> None:
    allow = tmp_path / "allow.txt"
    allow.write_text("CI healthos.ci.example:443\n", encoding="utf-8")
    conf = tmp_path / "ci.toml"
    conf.write_text(
        'country_code = "CI"\ntimezone = "Africa/Abidjan"\ncurrency = "XOF"\n'
        '[healthos]\nfhir_base_url = "https://healthos.ci.example/fhir"\ntimeout_seconds = 5\n'
        '[egress]\nendpoints = ["healthos.ci.example:443", "llm.example.com:443"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"llm\.example\.com"):
        load_deployment("CI", deploy_dir=tmp_path, allowlist_path=allow)


def test_deployment_rejects_allowlist_entry_not_declared(tmp_path: Path) -> None:
    # Une porte ouverte que personne ne déclare est une porte oubliée : refusée.
    allow = tmp_path / "allow.txt"
    allow.write_text("CI healthos.ci.example:443\nCI forgotten.ci.example:8443\n", encoding="utf-8")
    conf = tmp_path / "ci.toml"
    conf.write_text(
        'country_code = "CI"\ntimezone = "Africa/Abidjan"\ncurrency = "XOF"\n'
        '[healthos]\nfhir_base_url = "https://healthos.ci.example/fhir"\ntimeout_seconds = 5\n'
        '[egress]\nendpoints = ["healthos.ci.example:443"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"forgotten\.ci\.example"):
        load_deployment("CI", deploy_dir=tmp_path, allowlist_path=allow)


def test_deployment_rejects_wrong_timezone(tmp_path: Path) -> None:
    allow = tmp_path / "allow.txt"
    allow.write_text("SN healthos.sn.example:443\n", encoding="utf-8")
    conf = tmp_path / "sn.toml"
    conf.write_text(
        'country_code = "SN"\ntimezone = "Europe/Paris"\ncurrency = "XOF"\n'
        '[healthos]\nfhir_base_url = "https://healthos.sn.example/fhir"\ntimeout_seconds = 5\n'
        '[egress]\nendpoints = ["healthos.sn.example:443"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Africa/Dakar"):
        load_deployment("SN", deploy_dir=tmp_path, allowlist_path=allow)


def test_deployment_files_hold_no_secret() -> None:
    forbidden = ("password", "secret", "token", "api_key", "apikey")

    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                assert not any(word in key.lower() for word in forbidden), f"{path}.{key}"
                walk(value, f"{path}.{key}")

    for file in sorted(DEPLOY_DIR.glob("*.toml")):
        walk(tomllib.loads(file.read_text(encoding="utf-8")), file.name)
    assert {p.stem.upper() for p in DEPLOY_DIR.glob("*.toml")} == set(COUNTRIES)


def test_endpoint_parsing() -> None:
    assert Endpoint.parse("HealthOS.CI.example:443") == Endpoint("healthos.ci.example", 443)
    with pytest.raises(ValueError, match="port"):
        Endpoint.parse("healthos.ci.example:99999")
