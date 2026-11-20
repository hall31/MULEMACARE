"""Domaine personnalisé de marque blanche (CR-P3-02) : réservé, puis PROUVÉ avant d'être servi.

Un admin d'organisation déclare un domaine ; il n'est servi par la lecture publique qu'une fois
la propriété prouvée. Deux gardes indépendantes :

1. ``ReservedDomains`` refuse d'emblée (BRD-05) les noms qui ne peuvent appartenir à une
   organisation cliente : noms à usage spécial (RFC 6761/6762/9476 et assimilés : ``localhost``,
   ``.invalid``, ``.local``, ``.test``, ``.example``, ``.internal``, ``.onion``…), domaines de la
   plateforme MulemaCare, et chaque hôte de l'instance (lien de paiement public, HealthOS, bases,
   toute destination de la liste blanche) AVEC sa zone parente. Un sous-domaine d'un domaine
   réservé est réservé.
2. Preuve de propriété : l'organisation publie un enregistrement DNS TXT
   ``_mulemacare-verification.<domaine>`` = ``mulemacare-verification=<jeton>`` (jeton tiré par le
   serveur, 128 bits, propre au domaine déclaré). Tant que ce n'est pas fait, le domaine est « en
   attente de vérification » et n'est jamais servi.

La résolution DNS est un PORT (``DnsTxtResolver``). Implémentations fournies : ``NoDnsTxtResolver``
(défaut de l'application : rien n'est jamais prouvé, le domaine personnalisé reste désactivé,
l'identifiant public ``slug`` reste utilisable) et ``StaticDnsTxt`` (tests). Aucun appel réseau
ici : un résolveur réel devra passer par la liste blanche d'egress (revue humaine).
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol

VERIFICATION_LABEL: Final = "_mulemacare-verification"
VERIFICATION_PREFIX: Final = "mulemacare-verification="
TOKEN_BYTES: Final = 16
_MIN_LABELS_FOR_PARENT: Final = 3

# Noms à usage spécial ou non délégués : jamais le domaine d'une organisation cliente.
SPECIAL_USE: Final = frozenset(
    {
        "localhost",
        "invalid",
        "local",
        "test",
        "example",
        "internal",
        "onion",
        "arpa",
        "home.arpa",
        "alt",
        "lan",
        "home",
        "corp",
        "intranet",
        "private",
        "example.com",
        "example.net",
        "example.org",
    }
)
# Domaines de la plateforme (marque MulemaCare, HealthOS) : jamais réclamables par un client.
PLATFORM_ZONES: Final = frozenset(
    {
        "mulemacare.com",
        "mulemacare.ci",
        "mulemacare.sn",
        "mulemacare.net",
        "mulemacare.org",
        "mulemacare.app",
        "mulemacare.health",
    }
)


def _normalized(domain: str) -> str:
    return domain.strip().lower().rstrip(".")


def _is_name(host: str) -> bool:
    """Nom de domaine (pas une adresse IP) : au moins un point et une étiquette finale alpha."""
    labels = host.split(".")
    return len(labels) >= 2 and labels[-1].isalpha()  # noqa: PLR2004 — étiquette + TLD


@dataclass(frozen=True, slots=True)
class ReservedDomains:
    zones: frozenset[str]

    @classmethod
    def for_instance(cls, hosts: Iterable[str]) -> ReservedDomains:
        """Zones intégrées + chaque hôte de l'instance et sa zone parente."""
        zones = set(SPECIAL_USE | PLATFORM_ZONES)
        for raw in hosts:
            host = _normalized(raw)
            if not _is_name(host):
                continue
            zones.add(host)
            labels = host.split(".")
            if len(labels) >= _MIN_LABELS_FOR_PARENT:
                zones.add(".".join(labels[1:]))
        return cls(frozenset(zones))

    def reserves(self, domain: str) -> bool:
        wanted = _normalized(domain)
        return any(wanted == zone or wanted.endswith(f".{zone}") for zone in self.zones)


@dataclass(frozen=True, slots=True)
class VerificationRecord:
    record_type: Literal["TXT"]
    record_name: str
    record_value: str


def new_token() -> str:
    return secrets.token_hex(TOKEN_BYTES)


def verification_record(domain: str, token: str) -> VerificationRecord:
    return VerificationRecord(
        record_type="TXT",
        record_name=f"{VERIFICATION_LABEL}.{_normalized(domain)}",
        record_value=f"{VERIFICATION_PREFIX}{token}",
    )


class DnsTxtResolver(Protocol):
    async def txt_records(self, name: str) -> frozenset[str]:
        """Valeurs TXT publiées sous ``name`` (ensemble vide si rien ou introuvable)."""
        ...


class NoDnsTxtResolver:
    """Défaut : aucune résolution, aucune preuve ; le domaine personnalisé reste désactivé."""

    async def txt_records(self, name: str) -> frozenset[str]:
        del name
        return frozenset()


@dataclass
class StaticDnsTxt:
    """Implémentation de test : enregistrements TXT en mémoire."""

    records: dict[str, set[str]] = field(default_factory=dict)

    def publish(self, name: str, value: str) -> None:
        self.records.setdefault(_normalized(name), set()).add(value)

    def clear(self) -> None:
        self.records.clear()

    async def txt_records(self, name: str) -> frozenset[str]:
        return frozenset(self.records.get(_normalized(name), set()))


async def proves_ownership(resolver: DnsTxtResolver, domain: str, token: str) -> bool:
    expected = verification_record(domain, token)
    published = await resolver.txt_records(expected.record_name)
    return any(secrets.compare_digest(value.strip(), expected.record_value) for value in published)
