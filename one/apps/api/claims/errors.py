"""Erreurs métier du lot L5, à code stable du contrat (``ErrorCode`` de specs/openapi.yaml).

Le noyau (``api.core.errors``) ne connaît que ses propres codes et ne rend ni
``remaining_attempts`` ni ``retry_after_seconds`` ; L5 a donc son erreur et son gestionnaire
problem+json, enregistrés par ``install`` (même schéma que L3).
"""

from __future__ import annotations

from typing import Any, Final, Literal

from fastapi import Request, status
from fastapi.responses import JSONResponse

from api.core.context import request_id_of

PROBLEM_JSON: Final = "application/problem+json"

ClaimsCode = Literal[
    "ID-03", "ID-04", "ID-05", "ID-06", "ID-07", "CLM-01", "CLM-02", "IDEM-01", "IDEM-02",
    "NOT-01", "VAL-01", "RUL-02", "SYS-01",
]  # fmt: skip


class ClaimsError(Exception):
    def __init__(  # noqa: PLR0913 — champs du Problem du contrat
        self,
        code: ClaimsCode,
        status_code: int,
        message: str,
        action: str,
        *,
        remaining_attempts: int | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code: ClaimsCode = code
        self.status_code = status_code
        self.message = message
        self.action = action
        self.remaining_attempts = remaining_attempts
        self.retry_after_seconds = retry_after_seconds


def problem(error: ClaimsError, request_id: str) -> JSONResponse:
    body: dict[str, Any] = {
        "code": error.code,
        "message": error.message,
        "action": error.action,
        "request_id": request_id,
    }
    if error.remaining_attempts is not None:
        body["remaining_attempts"] = error.remaining_attempts
    if error.retry_after_seconds is not None:
        body["retry_after_seconds"] = error.retry_after_seconds
    return JSONResponse(
        body,
        status_code=error.status_code,
        media_type=PROBLEM_JSON,
        headers={"X-Request-ID": request_id},
    )


async def claims_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ClaimsError):  # enregistré pour ClaimsError seulement
        raise exc
    return problem(exc, request_id_of(request))


# --- Fabriques ---------------------------------------------------------------------------------


def not_found(message: str = "Élément introuvable.") -> ClaimsError:
    return ClaimsError(
        "NOT-01", status.HTTP_404_NOT_FOUND, message, "Vérifiez le lien ou revenez à la liste."
    )


def invalid(message: str, action: str = "Corrigez la demande puis recommencez.") -> ClaimsError:
    return ClaimsError("VAL-01", status.HTTP_422_UNPROCESSABLE_CONTENT, message, action)


def transition_forbidden(message: str) -> ClaimsError:
    return ClaimsError(
        "CLM-01",
        status.HTTP_409_CONFLICT,
        message,
        "Rechargez le dossier pour voir son état actuel.",
    )


def unknown_card() -> ClaimsError:
    return ClaimsError(
        "ID-06",
        status.HTTP_404_NOT_FOUND,
        "Aucune carte active ne correspond à ce code.",
        "Vérifiez le numéro sur la carte ou demandez une nouvelle carte à la mutuelle.",
    )


def card_blocked(retry_after_seconds: int, attempts: int, minutes: int) -> ClaimsError:
    return ClaimsError(
        "ID-04",
        status.HTTP_423_LOCKED,
        f"Carte bloquée pendant {minutes} minutes après {attempts} codes faux.",
        "Faites patienter l'adhérent ou contactez la mutuelle.",
        retry_after_seconds=retry_after_seconds,
    )


def wrong_code(remaining: int) -> ClaimsError:
    word = "essai" if remaining == 1 else "essais"
    return ClaimsError(
        "ID-03",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        f"Code incorrect. Il reste {remaining} {word}.",
        "Demandez à l'adhérent de relire le SMS, ou renvoyez le code.",
        remaining_attempts=remaining,
    )


def code_expired() -> ClaimsError:
    return ClaimsError(
        "ID-05",
        status.HTTP_410_GONE,
        "Ce code a expiré.",
        "Renvoyez un nouveau code à l'adhérent.",
    )


def identification_incomplete(
    message: str, status_code: int = status.HTTP_409_CONFLICT
) -> ClaimsError:
    return ClaimsError(
        "ID-07",
        status_code,
        message,
        "Reprenez l'identification au comptoir : carte, photo, puis code SMS.",
    )


def act_off_tariff(codes: list[str]) -> ClaimsError:
    return ClaimsError(
        "CLM-02",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        f"Acte(s) inconnu(s) de la nomenclature : {', '.join(codes)}.",
        "Choisissez les actes dans la liste du barème.",
    )
