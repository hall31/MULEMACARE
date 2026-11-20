"""Correspondance DÉCLARATIVE source → One, champ par champ.

Une ``ImportSpec`` décrit, pour chaque type de ligne de One (formule, version, garantie,
prestataire, adhérent, ayant droit, cotisation, dossier), le jeu de données de la source qui
l'alimente, la colonne de chaque champ canonique, les clés d'origine conservées dans
``external_ids`` et les références vers les autres types. Changer de source = changer des
données, pas du code. ``validate_spec`` refuse (IMP-06) un champ inconnu, un champ obligatoire
absent, et toute colonne au nom médical ou libre (diagnostic, description, motif, documents…) :
le secret médical (R6) commence à l'extraction.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from api.legacy_import.errors import ImportRefusedError

type Kind = Literal[
    "plan",
    "plan_version",
    "coverage",
    "provider",
    "member",
    "dependent",
    "contribution",
    "claim",
]

# Ordre de chargement : une ligne n'est écrite qu'après celles qu'elle référence.
LOAD_ORDER: Final[tuple[Kind, ...]] = (
    "plan",
    "plan_version",
    "coverage",
    "provider",
    "member",
    "dependent",
    "contribution",
    "claim",
)

# Champs canoniques (obligatoires, facultatifs) par type.
CANONICAL_FIELDS: Final[Mapping[Kind, tuple[frozenset[str], frozenset[str]]]] = {
    "plan": (frozenset({"code", "name"}), frozenset()),
    "plan_version": (
        frozenset(
            {
                "valid_from",
                "coverage_rate_percent",
                "family_annual_ceiling",
                "waiting_period_days",
                "monthly_contribution",
            }
        ),
        frozenset({"valid_to", "currency"}),
    ),
    "coverage": (frozenset({"category", "label"}), frozenset({"annual_limit", "currency"})),
    "provider": (frozenset({"name", "kind", "city", "country", "status"}), frozenset()),
    "member": (
        frozenset({"given_name", "family_name", "birth_date", "status", "enrolled_on"}),
        frozenset({"phone", "phone_country_code", "email", "beneficiaries_json"}),
    ),
    "dependent": (
        frozenset({"given_name", "family_name", "birth_date", "relationship"}),
        frozenset(),
    ),
    "contribution": (frozenset({"amount", "paid_on", "status"}), frozenset({"currency"})),
    "claim": (frozenset({"service_date", "total", "status"}), frozenset({"covered", "currency"})),
}

# Références obligatoires par type : rôle → types cibles admis.
REQUIRED_REFS: Final[Mapping[Kind, Mapping[str, frozenset[Kind]]]] = {
    "plan": {},
    "plan_version": {"plan": frozenset({"plan"})},
    "coverage": {"plan_version": frozenset({"plan_version"})},
    "provider": {},
    "member": {"plan": frozenset({"plan"})},
    "dependent": {"member": frozenset({"member"})},
    "contribution": {"member": frozenset({"member"})},
    "claim": {"member": frozenset({"member"}), "provider": frozenset({"provider"})},
}

# Colonnes jamais lues : médical, texte libre, pièces, secrets (R6, AGENTS.md).
FORBIDDEN_COLUMN: Final = re.compile(
    r"diagnos|icd|description|motif|reason|rejection|prescri|ordonnance|document|metadata"
    r"|note|specialt|invoice|kyc|licen[cs]e|identity_image|password|token|card_?number"
    r"|creditcard|avatar|photo",
    re.IGNORECASE,
)
_NAME: Final = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_COLUMN: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


@dataclass(frozen=True, slots=True)
class Dataset:
    """Jeu de données : ``<name>.csv`` (export), table ``name`` (dump) ou ``select`` (MySQL)."""

    name: str
    select: str


@dataclass(frozen=True, slots=True)
class Key:
    """Clé d'origine : ``name`` (subscription_number…) lue dans ``column``."""

    name: str
    column: str


@dataclass(frozen=True, slots=True)
class Ref:
    """Référence vers une ligne d'un autre type, par une de ses clés d'origine."""

    kind: Kind
    key: str
    column: str


@dataclass(frozen=True, slots=True)
class JsonDependents:
    """Ayants droit portés en JSON par l'adhésion (liste d'objets) : clé de chaque attribut."""

    given_name: str
    family_name: str
    birth_date: str
    relationship: str


@dataclass(frozen=True, slots=True)
class EntitySpec:
    kind: Kind
    dataset: Dataset
    keys: tuple[Key, ...]
    fields: Mapping[str, str]
    refs: Mapping[str, Ref] = field(default_factory=dict)
    # Champ canonique → constante DÉCLARÉE (jamais un défaut implicite), à valider par un humain.
    constants: Mapping[str, str] = field(default_factory=dict)
    # Vocabulaire de statuts (``statuses.STATUS_MAP``), pour les types qui en portent un.
    status_vocabulary: str | None = None
    # Adhérent : clés de la PERSONNE (titulaire), distinctes des clés du contrat.
    person_keys: tuple[Key, ...] = ()
    json_dependents: JsonDependents | None = None
    # Filtre déclaré : colonne → valeurs retenues ; les autres lignes sont hors périmètre.
    only_when: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def columns(self) -> set[str]:
        used = {k.column for k in (*self.keys, *self.person_keys)}
        used |= set(self.fields.values()) | {r.column for r in self.refs.values()}
        return used | set(self.only_when)


@dataclass(frozen=True, slots=True)
class ImportSpec:
    """Correspondance complète d'une source (``source`` = étiquette dans ``external_ids``)."""

    source: str
    version: str
    entities: Mapping[Kind, EntitySpec]
    # Vocabulaires déclarés (lien de parenté, type de prestataire, pays) : valeur → valeur One.
    vocabularies: Mapping[str, Mapping[str, str]] = field(default_factory=dict)


def _refuse(detail: str) -> ImportRefusedError:
    return ImportRefusedError("IMP-06", f"Corrigez la correspondance : {detail}.")


def _validate_entity(kind: Kind, entity: EntitySpec) -> None:
    if entity.kind != kind:
        raise _refuse(f"type {entity.kind} déclaré sous {kind}")
    required, optional = CANONICAL_FIELDS[kind]
    declared = set(entity.fields) | set(entity.constants)
    if unknown := declared - required - optional:
        raise _refuse(f"{kind} : champ(s) inconnu(s) {sorted(unknown)}")
    if missing := required - declared:
        raise _refuse(f"{kind} : champ(s) obligatoire(s) absent(s) {sorted(missing)}")
    if not entity.keys or any(not _NAME.fullmatch(k.name) for k in entity.keys):
        raise _refuse(f"{kind} : au moins une clé d'origine nommée est exigée")
    if any(k.name == "email" for k in (*entity.keys, *entity.person_keys)):
        raise _refuse(f"{kind} : l'adresse électronique n'est jamais une clé (ADR-006)")
    for role, targets in REQUIRED_REFS[kind].items():
        ref = entity.refs.get(role)
        if ref is None or ref.kind not in targets:
            raise _refuse(f"{kind} : référence « {role} » absente ou mal typée")
    if kind == "member" and not entity.person_keys:
        raise _refuse("member : clé de la personne (titulaire) exigée")
    if entity.status_vocabulary is None and kind in {"member", "contribution", "claim"}:
        raise _refuse(f"{kind} : vocabulaire de statuts exigé")
    for column in entity.columns():
        if not _COLUMN.fullmatch(column):
            raise _refuse(f"{kind} : nom de colonne invalide")
        if FORBIDDEN_COLUMN.search(column):
            raise _refuse(f"{kind} : colonne interdite (médicale, libre ou secrète)")
    if FORBIDDEN_COLUMN.search(entity.dataset.select):
        raise _refuse(f"{kind} : la requête lit une colonne interdite")
    if not _NAME.fullmatch(entity.dataset.name):
        raise _refuse(f"{kind} : nom de jeu de données invalide")


def validate_spec(spec: ImportSpec) -> ImportSpec:
    """Refuse (IMP-06) toute correspondance incomplète, ambiguë ou qui lirait du médical."""
    if not _NAME.fullmatch(spec.source):
        raise _refuse("étiquette de source invalide")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,39}", spec.version):
        raise _refuse("version invalide")
    for kind, entity in spec.entities.items():
        _validate_entity(kind, entity)
    if "member" not in spec.entities:
        raise _refuse("aucun adhérent déclaré")
    for entity in spec.entities.values():
        for ref in entity.refs.values():
            target = spec.entities.get(ref.kind)
            if target is None or ref.key not in {k.name for k in target.keys}:
                raise _refuse(f"référence vers {ref.kind}.{ref.key} sans clé correspondante")
    return spec
