"""Liste blanche FERMÉE des événements d'usage et règles par événement (CR-P2-01, CR-P2-02).

Le schéma de requête borne déjà chaque champ (énumérations, entiers). Ici, ce qui dépend de
l'événement : surfaces admises, variante admise ou exigée, étape exigée, durée interdite, admise
ou exigée et sa borne ; le rôle d'origine doit appartenir à l'utilisateur du jeton (403) et
correspondre à la surface (422).

Contributeur : la PERSONNE, pas la session (un rechargement de page tire une nouvelle session ;
compter des sessions laissait une personne seule franchir le seuil). L'empreinte stockée dans
``product_events.session_ref`` (nom de colonne conservé, aucune migration) est
``HMAC-SHA256(clé du serveur, organisation ‖ utilisateur du jeton)`` : stable pour une personne,
propre à l'organisation, impossible à recalculer sans la clé (hors base, hors dépôt). Rien de ce
que le client envoie n'y entre.

Identifiant de session : exactement 32 caractères hexadécimaux, validé puis écarté (ni stocké,
ni dérivé). Un identifiant qui est celui de l'utilisateur, de son organisation ou d'un attribut
de portée, ou qui n'est fait que de chiffres, est refusé.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal, get_args
from uuid import UUID

from api.core.errors import FieldError, RoleForbiddenError, ValidationFailedError
from api.core.permissions import Principal, Role
from api.metrics.schemas import EventName, ProductEventRequest, Variant

EVENT_NAMES: Final = frozenset(get_args(EventName.__value__))
VARIANTS: Final = frozenset(get_args(Variant.__value__))

ALL_SURFACES: Final = frozenset({"console", "comptoir", "espace_adherent"})
ADHERENT_SPACE: Final = frozenset({"espace_adherent"})
COUNTER: Final = frozenset({"comptoir"})
CONSOLE: Final = frozenset({"console"})

# Chaque rôle a exactement une surface : le rôle d'origine désigne l'écran.
SURFACE_ROLES: Final[Mapping[str, frozenset[Role]]] = MappingProxyType(
    {
        "console": frozenset(
            {
                Role.GESTIONNAIRE,
                Role.MEDECIN_CONSEIL,
                Role.ADMIN,
                Role.EMPLOYEUR,
                Role.ASSUREUR,
                Role.ADMIN_PLATEFORME,
            }
        ),
        "comptoir": frozenset({Role.CLINIQUE}),
        "espace_adherent": frozenset({Role.ADHERENT}),
    }
)


type DurationRule = Literal["interdite", "admise", "exigee"]

# Bornes à valider (CR-P2-02) : un écran de décision au comptoir au-delà de 5 min n'est plus une
# mesure d'affichage ; un accueil au-delà d'une heure n'est plus un parcours d'accueil.
COUNTER_MAX_DURATION_MS: Final = 300_000
ONBOARDING_MAX_DURATION_MS: Final = 3_600_000


@dataclass(frozen=True, slots=True)
class EventRule:
    """Ce qu'un événement admet. ``variants`` vide : aucune variante ; sinon elle est exigée.

    ``duration`` : une durée n'est admise que là où un indicateur ou le catalogue en documente
    l'usage ; ailleurs, un entier libre pourrait porter un identifiant (téléphone, numéro).
    """

    surfaces: frozenset[str]
    variants: frozenset[str] = frozenset()
    step: bool = False
    duration: DurationRule = "interdite"
    max_duration_ms: int = 0


EVENT_RULES: Final[Mapping[str, EventRule]] = MappingProxyType(
    {
        "onboarding_started": EventRule(ALL_SURFACES),
        "onboarding_step": EventRule(ALL_SURFACES, step=True),
        "onboarding_completed": EventRule(
            ALL_SURFACES, duration="admise", max_duration_ms=ONBOARDING_MAX_DURATION_MS
        ),
        "card_presented": EventRule(ADHERENT_SPACE, frozenset({"en_ligne", "hors_ligne"})),
        "counter_decision_shown": EventRule(
            COUNTER,
            frozenset({"accordee", "revue", "refusee"}),
            duration="exigee",
            max_duration_ms=COUNTER_MAX_DURATION_MS,
        ),
        "payment_link_created": EventRule(ADHERENT_SPACE | CONSOLE),
        "palette_opened": EventRule(CONSOLE, frozenset({"clavier", "bouton"})),
        "joe_question_asked": EventRule(CONSOLE, frozenset({"exemple", "saisie"})),
        "notification_opened": EventRule(ALL_SURFACES, frozenset({"sms", "whatsapp", "in_app"})),
        "offline_banner_seen": EventRule(COUNTER | ADHERENT_SPACE),
        "claim_tracking_viewed": EventRule(ADHERENT_SPACE),
    }
)

_DIGITS_ONLY: Final = re.compile(r"^[0-9]+$")
PERSON_REF_CONTEXT: Final = b"mulema.metrics.person.v1"


def _identifiers(principal: Principal) -> set[UUID]:
    found = {principal.user_id, principal.organization_id}
    for grant in principal.grants:
        found |= {
            value
            for value in (grant.provider_id, grant.employer_id, grant.member_id)
            if value is not None
        }
    return found


def _session_problem(session_id: str, principal: Principal) -> str | None:
    if _DIGITS_ONLY.fullmatch(session_id):
        return "Identifiant de session non aléatoire (chiffres seulement)."
    if any(identifier.hex in session_id for identifier in _identifiers(principal)):
        return "L'identifiant de session ne doit contenir aucun identifiant de personne."
    return None


def _duration_problem(event: ProductEventRequest, rule: EventRule) -> str | None:
    if event.duration_ms is None:
        return "Durée exigée pour cet événement." if rule.duration == "exigee" else None
    if rule.duration == "interdite":
        return "Cet événement n'admet aucune durée."
    if event.duration_ms > rule.max_duration_ms:
        return f"Durée de {rule.max_duration_ms} ms au plus pour cet événement."
    return None


def _rule_problems(event: ProductEventRequest, role: Role) -> dict[str, str]:
    rule = EVENT_RULES[event.name]
    problems: dict[str, str] = {}
    if event.surface not in rule.surfaces or role not in SURFACE_ROLES[event.surface]:
        problems["surface"] = "Écran non admis pour cet événement ou pour ce rôle."
    if rule.step != (event.step is not None):
        problems["step"] = "Étape exigée pour onboarding_step, interdite sinon."
    if rule.variants:
        if event.variant not in rule.variants:
            problems["variant"] = "Variante manquante ou non admise pour cet événement."
    elif event.variant is not None:
        problems["variant"] = "Cet événement n'admet aucune variante."
    duration = _duration_problem(event, rule)
    if duration is not None:
        problems["duration_ms"] = duration
    return problems


def check_event(event: ProductEventRequest, principal: Principal) -> None:
    """Rôle du jeton (AUTH-02), puis règles de l'événement et session (VAL-01, par champ)."""
    role = Role(event.role)
    if role not in principal.roles:
        raise RoleForbiddenError
    problems = _rule_problems(event, role)
    session = _session_problem(event.session_id, principal)
    if session is not None:
        problems["session_id"] = session
    if problems:
        raise ValidationFailedError(
            "Cet événement de mesure n'est pas admis.",
            "Corrigez l'événement envoyé par l'écran (liste du contrat d'API).",
            errors=tuple(FieldError(field, message) for field, message in sorted(problems.items())),
        )


def person_ref(key: bytes, organization_id: UUID, user_id: UUID) -> str:
    """Empreinte pseudonyme de la PERSONNE (utilisateur du jeton), propre à l'organisation.

    HMAC avec la clé du serveur : stable tant que la clé l'est (une personne qui recharge reste
    un seul contributeur), impossible à recalculer depuis la base seule.
    """
    message = PERSON_REF_CONTEXT + b":" + organization_id.bytes + user_id.bytes
    return hmac.new(key, message, hashlib.sha256).hexdigest()
