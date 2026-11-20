"""Configuration de déploiement par pays (``infra/deploy/<pays>.toml``), validée contre la
liste blanche : une instance ne déclare que des destinations de son pays, toutes listées.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import UnionType
from typing import Any

from api.integrations.egress import (
    ALLOWLIST_PATH,
    COUNTRIES,
    INFRA_DIR,
    EgressAllowlist,
    Endpoint,
    load_allowlist,
)
from api.integrations.healthos import HealthOSClient
from api.integrations.transport import GuardedHttpTransport, split_destination

DEPLOY_DIR = INFRA_DIR / "deploy"
COUNTRY_TIMEZONES = {"CI": "Africa/Abidjan", "SN": "Africa/Dakar"}
CURRENCY = "XOF"


@dataclass(frozen=True, slots=True)
class CountryDeployment:
    country_code: str
    timezone: str
    currency: str
    healthos_fhir_base_url: str
    healthos_timeout_seconds: float
    egress_endpoints: frozenset[Endpoint]
    allowlist: EgressAllowlist

    @property
    def healthos_endpoint(self) -> Endpoint:
        _, host, port, _ = split_destination(self.healthos_fhir_base_url)
        return Endpoint(host, port)


def _require(table: dict[str, Any], key: str, kind: type[Any] | UnionType, where: str) -> Any:  # noqa: ANN401
    value = table.get(key)
    if not isinstance(value, kind) or isinstance(value, bool):
        raise ValueError(f"{where} : clé {key!r} absente ou de mauvais type")
    return value


def load_deployment(
    country: str, *, deploy_dir: Path = DEPLOY_DIR, allowlist_path: Path = ALLOWLIST_PATH
) -> CountryDeployment:
    """Charge et valide la configuration d'un pays ; ``ValueError`` à la moindre incohérence."""
    if country not in COUNTRIES:
        raise ValueError(f"pays inconnu : {country!r}")
    path = deploy_dir / f"{country.lower()}.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    where = path.name

    if _require(data, "country_code", str, where) != country:
        raise ValueError(f"{where} : country_code doit valoir {country}")
    timezone = _require(data, "timezone", str, where)
    if timezone != COUNTRY_TIMEZONES[country]:
        raise ValueError(f"{where} : fuseau attendu {COUNTRY_TIMEZONES[country]}, lu {timezone}")
    if _require(data, "currency", str, where) != CURRENCY:
        raise ValueError(f"{where} : devise attendue {CURRENCY}")

    healthos = _require(data, "healthos", dict, where)
    base_url = _require(healthos, "fhir_base_url", str, f"{where} [healthos]")
    timeout = float(_require(healthos, "timeout_seconds", int | float, f"{where} [healthos]"))
    if not base_url.startswith("https://"):
        raise ValueError(f"{where} : HealthOS doit être joint en https")

    egress = _require(data, "egress", dict, where)
    raw_endpoints = _require(egress, "endpoints", list, f"{where} [egress]")
    declared = frozenset(Endpoint.parse(str(raw)) for raw in raw_endpoints)

    allowlist = load_allowlist(allowlist_path, country=country)
    missing = sorted(str(e) for e in declared - allowlist.endpoints)
    if missing:
        raise ValueError(f"{where} : destinations absentes de la liste blanche : {missing}")
    unused = sorted(str(e) for e in allowlist.endpoints - declared)
    if unused:
        raise ValueError(f"{where} : entrées de liste blanche non déclarées : {unused}")

    deployment = CountryDeployment(
        country_code=country,
        timezone=timezone,
        currency=CURRENCY,
        healthos_fhir_base_url=base_url,
        healthos_timeout_seconds=timeout,
        egress_endpoints=declared,
        allowlist=allowlist,
    )
    if deployment.healthos_endpoint not in declared:
        raise ValueError(f"{where} : l'adresse HealthOS n'est pas déclarée dans [egress]")
    return deployment


def build_healthos_client(deployment: CountryDeployment) -> HealthOSClient:
    """Client HealthOS dont le transport est limité à la liste blanche du pays."""
    transport = GuardedHttpTransport(
        deployment.allowlist, timeout_seconds=deployment.healthos_timeout_seconds
    )
    return HealthOSClient(base_url=deployment.healthos_fhir_base_url, transport=transport)
