"""Erreurs métier typées à code stable (``ErrorCode`` de specs/openapi.yaml).

Chaque erreur porte un code stable, un statut HTTP, un message en français simple et l'action à
faire. Elles sont rendues en ``application/problem+json`` par ``api.core.app``. Aucune donnée
identifiante ni médicale ne doit entrer dans ``message`` ou ``action``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar


class ErrorCode(StrEnum):
    """Codes stables utilisés par le noyau (sous-ensemble de ``ErrorCode`` du contrat)."""

    AUTH_01 = "AUTH-01"
    AUTH_02 = "AUTH-02"
    SEC_01 = "SEC-01"
    VAL_01 = "VAL-01"
    NOT_01 = "NOT-01"
    INT_01 = "INT-01"
    SYS_01 = "SYS-01"
    # Phase 3 (CR-P3-01) : marque blanche et accueil d'organisation.
    BRD_01 = "BRD-01"
    BRD_02 = "BRD-02"
    BRD_03 = "BRD-03"
    BRD_04 = "BRD-04"
    BRD_05 = "BRD-05"
    BRD_06 = "BRD-06"
    ORG_01 = "ORG-01"
    ORG_02 = "ORG-02"
    # L10 (CR-L10-01) : limitation de débit.
    RATE_01 = "RATE-01"


@dataclass(frozen=True, slots=True)
class FieldError:
    """Détail d'une erreur de validation, par champ (chemin pointé, sans valeur saisie)."""

    field: str
    message: str


class DomainError(Exception):
    """Base des erreurs métier. Les sous-classes fixent code, statut, message et action."""

    code: ClassVar[ErrorCode]
    status_code: ClassVar[int]
    default_message: ClassVar[str]
    default_action: ClassVar[str]

    def __init__(
        self,
        message: str | None = None,
        action: str | None = None,
        *,
        errors: tuple[FieldError, ...] = (),
    ) -> None:
        self.message = message or self.default_message
        self.action = action or self.default_action
        self.errors = errors
        super().__init__(self.code.value)


class NotAuthenticatedError(DomainError):
    code = ErrorCode.AUTH_01
    status_code = 401
    default_message = "Votre session a expiré ou n'est pas valide."
    default_action = "Reconnectez-vous puis recommencez."


class RoleForbiddenError(DomainError):
    code = ErrorCode.AUTH_02
    status_code = 403
    default_message = "Votre rôle ne permet pas cette action."
    default_action = "Demandez l'accès à l'administrateur de votre organisation."


class MedicalSecretError(DomainError):
    code = ErrorCode.SEC_01
    status_code = 403
    default_message = "Le motif médical est réservé au médecin-conseil."
    default_action = "Demandez l'avis du médecin-conseil depuis le dossier."


class NotFoundError(DomainError):
    """Introuvable OU hors du périmètre de l'utilisateur : on ne distingue pas les deux."""

    code = ErrorCode.NOT_01
    status_code = 404
    default_message = "Élément introuvable."
    default_action = "Vérifiez le lien ou revenez à la liste."


class ValidationFailedError(DomainError):
    code = ErrorCode.VAL_01
    status_code = 422
    default_message = "Certaines informations sont invalides ou manquantes."
    default_action = "Corrigez les champs signalés puis recommencez."


class DuplicateUserError(DomainError):
    """Sujet d'identité déjà rattaché à l'organisation (409 ; code VAL-01, voir CR-L1-01)."""

    code = ErrorCode.VAL_01
    status_code = 409
    default_message = "Cet identifiant de connexion est déjà rattaché à un utilisateur."
    default_action = "Retrouvez l'utilisateur existant dans la liste et modifiez ses rôles."


class RoleRevocationUnavailableError(DomainError):
    """Retrait de rôle impossible tant que le contrat n'y donne pas droit (CR-L1-02)."""

    code = ErrorCode.VAL_01
    status_code = 409
    default_message = "Le retrait d'un rôle n'est pas encore possible."
    default_action = "Désactivez l'utilisateur ou contactez l'équipe technique."


class UpstreamUnavailableError(DomainError):
    code = ErrorCode.INT_01
    status_code = 502
    default_message = "Le dossier médical est momentanément indisponible."
    default_action = "Réessayez dans quelques minutes."


class InternalError(DomainError):
    code = ErrorCode.SYS_01
    status_code = 500
    default_message = "Une erreur interne est survenue."
    default_action = "Réessayez ; si le problème persiste, contactez le support avec ce numéro."


class RateLimitedError(DomainError):
    """Trop de demandes en peu de temps (429, RATE-01, CR-L10-01) ; ``retry_after_seconds``
    est renvoyé dans le corps et dans l'en-tête ``Retry-After``."""

    code = ErrorCode.RATE_01
    status_code = 429
    default_message = "Trop de demandes en peu de temps."
    default_action = "Patientez quelques instants puis recommencez."

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__()
        self.retry_after_seconds = max(1, retry_after_seconds)
