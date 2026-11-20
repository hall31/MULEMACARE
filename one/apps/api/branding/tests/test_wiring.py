"""Montage de la marque blanche (CR-P3-02) : ce que ``create_app`` réserve et admet.

- Domaines réservés : l'hôte du lien de paiement public et chaque destination de la liste
  blanche d'egress (HealthOS…), avec leur zone parente, en plus des zones intégrées.
- Hôtes de logo : la liste DÉDIÉE des ports de la marque, jamais la liste blanche d'egress
  (HealthOS y figure : le serveur le joint, un navigateur ne doit jamais y charger d'image).
Données fictives.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from api.branding.logo import LogoRejectedError, validate_logo
from api.branding.service import BrandingPorts, BrandingRuntime
from api.core.app import AppModules, _branding_runtime
from api.core.settings import Settings
from api.integrations.egress import EgressAllowlist, Endpoint

HEALTHOS = "healthos.ci.sante-fictive.ci"
LOGOS = "logos.assurance-fictive.ci"


def _runtime(ports: BrandingPorts) -> BrandingRuntime:
    settings = Settings(
        database_url="postgresql+psycopg:///inutilise",
        egress_allowlist=EgressAllowlist(frozenset({Endpoint(HEALTHOS, 443)})),
    )
    modules = SimpleNamespace(
        payments=SimpleNamespace(
            config=SimpleNamespace(public_base_url="https://paiement.mutuelle-fictive.ci/p")
        ),
        metrics=SimpleNamespace(clock=None),
        branding=ports,
    )
    return _branding_runtime(settings, cast(AppModules, modules))


@pytest.mark.parametrize(
    "domain",
    [
        "paiement.mutuelle-fictive.ci",  # lien de paiement public
        "mutuelle-fictive.ci",  # sa zone parente
        "x.paiement.mutuelle-fictive.ci",
        HEALTHOS,
        "ci.sante-fictive.ci",
        "reserve.exploitation-fictive.ci",  # ajouté par l'exploitation
    ],
)
def test_hotes_de_l_instance_reserves(domain: str) -> None:
    runtime = _runtime(BrandingPorts(reserved_hosts=("reserve.exploitation-fictive.ci",)))
    assert runtime.reserved.reserves(domain)


def test_logo_jamais_vers_la_liste_d_egress() -> None:
    runtime = _runtime(BrandingPorts(logo_hosts=EgressAllowlist(frozenset({Endpoint(LOGOS, 443)}))))
    hosts = runtime.logo_hosts
    assert validate_logo("url", f"https://{LOGOS}/l.png", hosts)
    with pytest.raises(LogoRejectedError):
        validate_logo("url", f"https://{HEALTHOS}/l.png", hosts)


def test_par_defaut_aucun_hote_de_logo() -> None:
    hosts = _runtime(BrandingPorts()).logo_hosts
    with pytest.raises(LogoRejectedError):
        validate_logo("url", f"https://{HEALTHOS}/l.png", hosts)
    assert validate_logo("url", "/assets/logo.svg", hosts)
