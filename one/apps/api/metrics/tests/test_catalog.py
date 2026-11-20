"""Liste blanche FERMÉE des événements produit et pseudonymisation (P2, CR-P2-01, CR-P2-02).

Fonctions pures, sans base : nom hors liste, champ inconnu, texte libre, propriété non admise
pour l'événement (durée comprise), surface incompatible avec le rôle, identifiant de session qui
n'est pas exactement 32 caractères hexadécimaux ou qui ressemble à un identifiant de personne.
Tout refus est une erreur typée (VAL-01 422, AUTH-02 403). Le contributeur compté est une
empreinte HMAC de l'UTILISATEUR DU JETON, avec une clé du serveur : rien du client n'y entre.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from api.core.errors import RoleForbiddenError, ValidationFailedError
from api.core.permissions import Principal, Role, RoleGrant
from api.metrics.catalog import (
    EVENT_NAMES,
    EVENT_RULES,
    SURFACE_ROLES,
    VARIANTS,
    check_event,
    person_ref,
)
from api.metrics.schemas import ProductEventRequest

SESSION = "3f9c2a7be41d48c09a5e6b1f0d2c8e74"  # 16 octets aléatoires en hexadécimal (fictif)
ORG = UUID("00000000-0000-4000-8000-0000000000e1")
KEY = bytes.fromhex("5a" * 32)  # clé FICTIVE de test, jamais utilisée hors des tests


def _event(**overrides: Any) -> ProductEventRequest:  # noqa: ANN401
    body: dict[str, Any] = {
        "name": "onboarding_started",
        "surface": "espace_adherent",
        "role": "adherent",
        "session_id": SESSION,
    } | overrides
    return ProductEventRequest.model_validate(body)


def _principal(*roles: Role) -> Principal:
    grants = tuple(
        RoleGrant(
            role,
            provider_id=uuid4() if role is Role.CLINIQUE else None,
            employer_id=uuid4() if role is Role.EMPLOYEUR else None,
            member_id=uuid4() if role is Role.ADHERENT else None,
        )
        for role in roles
    )
    return Principal(user_id=uuid4(), organization_id=ORG, grants=grants)


# --- Liste blanche fermée ----------------------------------------------------------------------


def test_liste_blanche_exacte() -> None:
    """Égalité stricte : ajouter un événement oblige à modifier ce test ET le contrat."""
    assert (
        frozenset(
            {
                "onboarding_started",
                "onboarding_step",
                "onboarding_completed",
                "card_presented",
                "counter_decision_shown",
                "payment_link_created",
                "palette_opened",
                "joe_question_asked",
                "notification_opened",
                "offline_banner_seen",
                "claim_tracking_viewed",
            }
        )
        == EVENT_NAMES
    )
    assert frozenset(EVENT_RULES) == EVENT_NAMES
    assert set(SURFACE_ROLES) == {"console", "comptoir", "espace_adherent"}
    # Chaque rôle a exactement une surface : le rôle d'origine désigne l'écran.
    owners = [role for roles in SURFACE_ROLES.values() for role in roles]
    assert sorted(owners) == sorted(Role)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"name": "page_viewed"}, id="nom-hors-liste"),
        pytest.param({"name": "ONBOARDING_STARTED"}, id="nom-casse"),
        pytest.param({"surface": "site_public"}, id="surface-inconnue"),
        pytest.param({"role": "payeur"}, id="role-inconnu"),
        pytest.param({"free_text": "Awa a cliqué"}, id="champ-inconnu"),
        pytest.param({"user_id": str(uuid4())}, id="identifiant-utilisateur"),
        pytest.param({"member_id": str(uuid4())}, id="identifiant-adherent"),
        pytest.param({"organization_id": str(uuid4())}, id="organisation-du-client"),
        pytest.param({"properties": {"screen": "accueil"}}, id="objet-libre"),
        pytest.param({"variant": "Awa Fictif, +2250700000000"}, id="texte-libre-en-variante"),
        pytest.param({"duration_ms": "1200"}, id="duree-en-texte"),
        pytest.param({"duration_ms": True}, id="duree-booleen"),
        pytest.param({"duration_ms": 12.5}, id="duree-flottante"),
        pytest.param({"duration_ms": -1}, id="duree-negative"),
        pytest.param({"duration_ms": 3_600_001}, id="duree-hors-borne"),
        pytest.param({"step": 0}, id="etape-zero"),
        pytest.param({"step": 21}, id="etape-hors-borne"),
        pytest.param({"session_id": "court"}, id="session-trop-courte"),
        pytest.param({"session_id": "a" * 31}, id="session-31-hex"),
        pytest.param({"session_id": "a" * 33}, id="session-33-hex"),
        pytest.param({"session_id": SESSION.upper()}, id="session-majuscules"),
        pytest.param({"session_id": "k3Jd9-QpL2x_7HvN0aZtRw"}, id="session-base64url"),
        pytest.param({"session_id": "k3Jd9-QpL2x_7HvN0aZtRwk3Jd9-QpL2"}, id="session-texte-32"),
        pytest.param({"session_id": str(uuid4())}, id="session-uuid-avec-tirets"),
        pytest.param({"session_id": "awa.fictif@exemple.invalid1"}, id="session-courriel"),
        pytest.param({"session_id": "Awa Fictif 0700000000 abc"}, id="session-avec-espaces"),
        pytest.param({"session_id": SESSION + "\n"}, id="session-fin-de-ligne"),
    ],
)
def test_le_schema_refuse_tout_hors_liste(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _event(**overrides)


# --- Règles par événement ----------------------------------------------------------------------


def _problems(event: ProductEventRequest, principal: Principal) -> list[str]:
    try:
        check_event(event, principal)
    except ValidationFailedError as exc:
        return sorted(e.field for e in exc.errors)
    return []


ADHERENT = _principal(Role.ADHERENT)
CLINIQUE = _principal(Role.CLINIQUE)
GESTIONNAIRE = _principal(Role.GESTIONNAIRE)


@pytest.mark.parametrize(
    ("principal", "overrides", "fields"),
    [
        pytest.param(ADHERENT, {}, [], id="demarrage-accepte"),
        pytest.param(ADHERENT, {"name": "onboarding_step", "step": 2}, [], id="etape-acceptee"),
        pytest.param(ADHERENT, {"name": "onboarding_step"}, ["step"], id="etape-manquante"),
        pytest.param(ADHERENT, {"step": 2}, ["step"], id="etape-non-admise"),
        pytest.param(
            ADHERENT, {"name": "card_presented", "variant": "hors_ligne"}, [], id="carte-acceptee"
        ),
        pytest.param(ADHERENT, {"name": "card_presented"}, ["variant"], id="variante-manquante"),
        pytest.param(
            ADHERENT,
            {"name": "card_presented", "variant": "clavier"},
            ["variant"],
            id="variante-d-un-autre-evenement",
        ),
        pytest.param(ADHERENT, {"variant": "sms"}, ["variant"], id="variante-non-admise"),
        pytest.param(
            CLINIQUE,
            {
                "name": "counter_decision_shown",
                "surface": "comptoir",
                "role": "clinique",
                "variant": "accordee",
                "duration_ms": 6200,
            },
            [],
            id="decision-comptoir-acceptee",
        ),
        pytest.param(
            CLINIQUE,
            {
                "name": "counter_decision_shown",
                "surface": "comptoir",
                "role": "clinique",
                "variant": "accordee",
            },
            ["duration_ms"],
            id="decision-sans-duree",
        ),
        pytest.param(
            ADHERENT,
            {"name": "counter_decision_shown", "variant": "accordee", "duration_ms": 10},
            ["surface"],
            id="decision-hors-comptoir",
        ),
        pytest.param(
            ADHERENT, {"surface": "console"}, ["surface"], id="surface-incompatible-avec-le-role"
        ),
        pytest.param(
            GESTIONNAIRE,
            {
                "name": "joe_question_asked",
                "surface": "console",
                "role": "gestionnaire",
                "variant": "saisie",
            },
            [],
            id="question-joe-sans-texte",
        ),
        pytest.param(
            GESTIONNAIRE,
            {"name": "palette_opened", "surface": "espace_adherent", "role": "gestionnaire"},
            ["surface", "variant"],
            id="palette-hors-console",
        ),
    ],
)
def test_regles_par_evenement(
    principal: Principal, overrides: dict[str, Any], fields: list[str]
) -> None:
    assert _problems(_event(**overrides), principal) == fields


def test_chaque_variante_est_rattachee_a_un_evenement() -> None:
    attached = frozenset().union(*(rule.variants for rule in EVENT_RULES.values()))
    assert attached == VARIANTS


def test_le_role_d_origine_doit_etre_celui_du_jeton() -> None:
    """Un adhérent qui se déclare gestionnaire : 403, pas une simple validation."""
    event = _event(surface="console", role="gestionnaire")
    with pytest.raises(RoleForbiddenError):
        check_event(event, ADHERENT)


def test_utilisateur_a_plusieurs_roles_choisit_le_sien() -> None:
    both = _principal(Role.GESTIONNAIRE, Role.MEDECIN_CONSEIL)
    check_event(_event(surface="console", role="medecin_conseil"), both)
    with pytest.raises(RoleForbiddenError):
        check_event(_event(surface="console", role="admin"), both)


# --- Identifiant de session : jamais un identifiant de personne --------------------------------


def test_session_accepte_exactement_32_hexadecimaux() -> None:
    assert _event(session_id=secrets.token_hex(16)).session_id is not None
    assert _problems(_event(), ADHERENT) == []


def test_session_qui_est_l_identifiant_de_l_utilisateur_refusee() -> None:
    """32 hexadécimaux, donc admis par le schéma : c'est la règle qui le refuse."""
    assert _problems(_event(session_id=ADHERENT.user_id.hex), ADHERENT) == ["session_id"]


@pytest.mark.parametrize("attribute", ["organization", "member"])
def test_session_qui_est_un_identifiant_de_portee_refusee(attribute: str) -> None:
    member = ADHERENT.grants[0].member_id
    assert member is not None
    raw = ADHERENT.organization_id if attribute == "organization" else member
    assert _problems(_event(session_id=raw.hex), ADHERENT) == ["session_id"]


def test_session_uniquement_numerique_refusee() -> None:
    """Un numéro (téléphone, carte) n'est pas un tirage aléatoire."""
    assert _problems(_event(session_id="22507000001234567890123456789012"), ADHERENT) == [
        "session_id"
    ]


# --- Durée : seulement pour les événements qui la mesurent -------------------------------------

DURATION_EVENTS = {"counter_decision_shown", "onboarding_completed"}


def test_seuls_deux_evenements_admettent_une_duree() -> None:
    assert {name for name, rule in EVENT_RULES.items() if rule.duration != "interdite"} == (
        DURATION_EVENTS
    )
    assert EVENT_RULES["counter_decision_shown"].duration == "exigee"
    assert EVENT_RULES["onboarding_completed"].duration == "admise"


def _valid_body(name: str) -> tuple[Principal, dict[str, Any]]:
    """Corps valide (hors durée) de chaque événement, sur une surface admise."""
    rule = EVENT_RULES[name]
    surface = sorted(rule.surfaces)[0]
    role = sorted(SURFACE_ROLES[surface])[0]
    body: dict[str, Any] = {"name": name, "surface": surface, "role": role.value}
    if rule.variants:
        body["variant"] = sorted(rule.variants)[0]
    if rule.step:
        body["step"] = 1
    return _principal(role), body


@pytest.mark.parametrize("name", sorted(EVENT_NAMES - DURATION_EVENTS))
def test_duree_refusee_ailleurs(name: str) -> None:
    """Une durée sur un événement qui n'en mesure pas pourrait porter un identifiant ; même 0
    (refusée par la règle, pas seulement par une borne)."""
    principal, body = _valid_body(name)
    assert _problems(_event(**body), principal) == []
    for duration in (0, 1234):
        assert _problems(_event(**body, duration_ms=duration), principal) == ["duration_ms"]


@pytest.mark.parametrize(
    ("name", "duration", "fields"),
    [
        pytest.param("counter_decision_shown", 0, [], id="comptoir-zero"),
        pytest.param("counter_decision_shown", 300_000, [], id="comptoir-cinq-minutes"),
        pytest.param("counter_decision_shown", 300_001, ["duration_ms"], id="comptoir-au-dela"),
        pytest.param("onboarding_completed", None, [], id="accueil-sans-duree"),
        pytest.param("onboarding_completed", 3_600_000, [], id="accueil-une-heure"),
    ],
)
def test_bornes_de_duree_par_evenement(name: str, duration: int | None, fields: list[str]) -> None:
    principal, body = _valid_body(name)
    if duration is not None:
        body["duration_ms"] = duration
    assert _problems(_event(**body), principal) == fields


# --- Contributeur : empreinte HMAC de l'utilisateur, clé du serveur ------------------------------


def test_empreinte_de_personne_stable_et_propre_a_la_cle() -> None:
    user = uuid4()
    ref = person_ref(KEY, ORG, user)
    assert len(ref) == 64
    assert int(ref, 16) >= 0
    assert user.hex not in ref
    assert person_ref(KEY, ORG, user) == ref  # même personne, même empreinte (rechargements)
    assert person_ref(KEY, ORG, uuid4()) != ref  # une autre personne
    assert person_ref(KEY, uuid4(), user) != ref  # propre à l'organisation
    assert person_ref(bytes.fromhex("a5" * 32), ORG, user) != ref  # clé tournée


def test_empreinte_non_recalculable_sans_la_cle() -> None:
    """Un hachage SANS secret (ancienne empreinte) se recalcule depuis la base : refusé."""
    user = uuid4()
    ref = person_ref(KEY, ORG, user)
    for material in (f"{ORG}:{user}", f"{ORG}{user}", user.hex, f"{ORG.hex}{user.hex}"):
        assert hashlib.sha256(material.encode()).hexdigest() != ref
    assert hashlib.sha256(ORG.bytes + user.bytes).hexdigest() != ref
