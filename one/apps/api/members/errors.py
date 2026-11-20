"""Erreurs métier du lot L4 (adhésions, cotisations), à code stable du contrat.

Le noyau (L1) ne déclare qu'un sous-ensemble des codes de ``ErrorCode`` (specs/openapi.yaml) :
MBR-01, IDEM-01, IDEM-02, PAY-01, PAY-02 et PAY-03 n'y figurent pas. Ce module porte donc sa
propre erreur, rendue au même format ``application/problem+json`` (code, message, action,
request_id) par ``membership_error_handler``. Aucun message ne contient de donnée identifiante.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from fastapi import Request, status
from fastapi.responses import JSONResponse

from api.core.context import request_id_of

logger = logging.getLogger(__name__)

PROBLEM_JSON: Final = "application/problem+json"
REQUEST_ID_HEADER: Final = "X-Request-ID"


@dataclass(frozen=True, slots=True)
class FieldProblem:
    """Erreur de validation d'un champ (chemin pointé, jamais la valeur saisie)."""

    field: str
    message: str


class MembershipError(Exception):
    """Erreur métier typée : code stable, statut HTTP, message et action en français."""

    def __init__(
        self,
        code: str,
        http_status: int,
        message: str,
        action: str,
        *,
        errors: tuple[FieldProblem, ...] = (),
    ) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.message = message
        self.action = action
        self.errors = errors


def not_found() -> MembershipError:
    """Introuvable OU hors de l'organisation : on ne distingue pas les deux (NOT-01)."""
    return MembershipError(
        "NOT-01",
        status.HTTP_404_NOT_FOUND,
        "Élément introuvable.",
        "Vérifiez le lien ou revenez à la liste.",
    )


def invalid(field: str, message: str) -> MembershipError:
    return MembershipError(
        "VAL-01",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Certaines informations sont invalides ou manquantes.",
        "Corrigez les champs signalés puis recommencez.",
        errors=(FieldProblem(field, message),),
    )


def status_change_refused(message: str, action: str) -> MembershipError:
    return MembershipError("MBR-01", status.HTTP_409_CONFLICT, message, action)


def state_conflict(message: str, action: str) -> MembershipError:
    """État incompatible sans code dédié au contrat (même choix que L1 : 409 + VAL-01)."""
    return MembershipError("VAL-01", status.HTTP_409_CONFLICT, message, action)


def idempotency_mismatch() -> MembershipError:
    return MembershipError(
        "IDEM-01",
        status.HTTP_409_CONFLICT,
        "Cette clé d'idempotence a déjà servi pour une autre demande.",
        "Générez une nouvelle clé pour une nouvelle demande.",
    )


def idempotency_in_progress() -> MembershipError:
    return MembershipError(
        "IDEM-02",
        status.HTTP_409_CONFLICT,
        "Cette demande est déjà en cours de traitement.",
        "Patientez quelques secondes puis recommencez avec la même clé.",
    )


def bad_signature() -> MembershipError:
    return MembershipError(
        "PAY-01",
        status.HTTP_401_UNAUTHORIZED,
        "Signature de la notification de paiement invalide.",
        "Vérifiez le secret de signature configuré pour ce canal.",
    )


def amount_mismatch() -> MembershipError:
    return MembershipError(
        "PAY-02",
        status.HTTP_409_CONFLICT,
        "Le montant notifié ne correspond pas au paiement attendu.",
        "Vérifiez la transaction chez le canal de paiement ; rien n'a été enregistré.",
    )


def link_gone() -> MembershipError:
    return MembershipError(
        "PAY-03",
        status.HTTP_410_GONE,
        "Ce lien de paiement a expiré ou a déjà servi.",
        "Demandez un nouveau lien à l'adhérent ou à la mutuelle.",
    )


def unavailable(what: str) -> MembershipError:
    return MembershipError(
        "SYS-01",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        f"{what} momentanément indisponible.",
        "Réessayez ; si le problème persiste, contactez le support avec ce numéro.",
    )


async def membership_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """``MembershipError`` → ``application/problem+json`` (même forme que le noyau)."""
    request_id = request_id_of(request)
    if not isinstance(exc, MembershipError):  # pragma: no cover — enregistré pour ce type seul
        raise exc
    if exc.http_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error("membership.unavailable", extra={"code": exc.code, "request_id": request_id})
    body: dict[str, object] = {
        "code": exc.code,
        "message": exc.message,
        "action": exc.action,
        "request_id": request_id,
    }
    if exc.errors:
        body["errors"] = [{"field": e.field, "message": e.message} for e in exc.errors]
    return JSONResponse(
        body,
        status_code=exc.http_status,
        media_type=PROBLEM_JSON,
        headers={REQUEST_ID_HEADER: request_id},
    )
