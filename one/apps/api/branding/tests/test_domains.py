"""Domaine personnalisé (CR-P3-02) : réservé, puis prouvé par l'organisation avant d'être servi.

- Domaines réservés : noms à usage spécial (``localhost``, ``.invalid``, ``.local``,
  ``.internal``…), domaines de la plateforme MulemaCare, et chaque hôte de l'instance (lien de
  paiement public, HealthOS et autres destinations de la liste blanche) AVEC sa zone parente.
  Un sous-domaine d'un domaine réservé est réservé.
- Preuve de propriété : enregistrement DNS TXT ``_mulemacare-verification.<domaine>`` portant
  ``mulemacare-verification=<jeton>`` ; le jeton est tiré par le serveur (128 bits).
- La résolution DNS est un PORT : ``NoDnsTxtResolver`` (défaut, rien n'est jamais prouvé, le
  domaine reste désactivé) et ``StaticDnsTxt`` (tests). Aucun appel réseau ici.
Données fictives.
"""

from __future__ import annotations

import asyncio
import re

import pytest

from api.branding.domains import (
    NoDnsTxtResolver,
    ReservedDomains,
    StaticDnsTxt,
    new_token,
    proves_ownership,
    verification_record,
)

INSTANCE = ReservedDomains.for_instance(
    [
        "payer.mulemacare.invalid",
        "app.mulemacare-pay.ci",
        "healthos.ci.sante-fictive.ci",
        "127.0.0.1",
    ]
)


@pytest.mark.parametrize(
    "domain",
    [
        "payer.mulemacare.invalid",
        "mulemacare.invalid",
        "x.payer.mulemacare.invalid",
        "mulemacare.com",
        "www.mulemacare.com",
        "mulemacare.ci",
        "app.mulemacare-pay.ci",
        "mulemacare-pay.ci",
        "evil.mulemacare-pay.ci",
        "healthos.ci.sante-fictive.ci",
        "ci.sante-fictive.ci",
        "foo.localhost",
        "intranet.local",
        "a.test",
        "assurance.example",
        "example.com",
        "insurance-db.ci.mulemacare.internal",
        "x.onion",
        "MULEMACARE.COM",
        "mulemacare.com.",
    ],
)
def test_domaine_reserve(domain: str) -> None:
    assert INSTANCE.reserves(domain)


@pytest.mark.parametrize(
    "domain",
    ["sante.assurance-fictive.ci", "b.fictif.ci", "mulemacare.com.evil.ci", "notmulemacare.com"],
)
def test_domaine_libre(domain: str) -> None:
    assert not INSTANCE.reserves(domain)


def test_mutation_hotes_de_l_instance_ignores() -> None:
    """Témoin : sans les hôtes de l'instance, le domaine du lien de paiement serait libre."""
    bare = ReservedDomains.for_instance([])
    assert not bare.reserves("app.mulemacare-pay.ci")
    assert INSTANCE.reserves("app.mulemacare-pay.ci")


def test_enregistrement_de_verification() -> None:
    token = new_token()
    assert re.fullmatch(r"[0-9a-f]{32}", token)
    assert new_token() != token
    record = verification_record("sante.assurance-fictive.ci", token)
    assert record.record_type == "TXT"
    assert record.record_name == "_mulemacare-verification.sante.assurance-fictive.ci"
    assert record.record_value == f"mulemacare-verification={token}"


def test_preuve_par_le_port_dns() -> None:
    token = new_token()
    record = verification_record("sante.assurance-fictive.ci", token)
    dns = StaticDnsTxt()
    assert not asyncio.run(proves_ownership(dns, "sante.assurance-fictive.ci", token))
    dns.publish(record.record_name, "v=spf1 -all")
    dns.publish(record.record_name, f"mulemacare-verification={new_token()}")  # autre jeton
    assert not asyncio.run(proves_ownership(dns, "sante.assurance-fictive.ci", token))
    dns.publish(record.record_name, record.record_value)
    assert asyncio.run(proves_ownership(dns, "sante.assurance-fictive.ci", token))
    # Le jeton publié sous un AUTRE nom ne prouve rien.
    other = StaticDnsTxt()
    other.publish("sante.assurance-fictive.ci", record.record_value)
    assert not asyncio.run(proves_ownership(other, "sante.assurance-fictive.ci", token))


def test_sans_resolveur_rien_n_est_jamais_prouve() -> None:
    token = new_token()
    assert not asyncio.run(proves_ownership(NoDnsTxtResolver(), "b.fictif.ci", token))
