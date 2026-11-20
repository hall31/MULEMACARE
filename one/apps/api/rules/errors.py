"""Erreurs métier du moteur de règles, à code stable (specs/openapi.yaml, ErrorCode).

``http_status`` est le statut rendu par les routes L2 (``api.rules.routes``) ; le moteur, lui,
n'en dépend pas.
"""

from __future__ import annotations

from typing import ClassVar


class RulesError(Exception):
    """Erreur du moteur : ``code`` stable, ``message`` et ``action`` en français simple."""

    code: str = "SYS-01"
    http_status: ClassVar[int] = 500

    def __init__(self, message: str, action: str) -> None:
        super().__init__(f"{self.code} : {message}")
        self.message = message
        self.action = action


class NoVersionInForceError(RulesError):
    """Aucune version publiée ne couvre la date du soin (produit ou règle)."""

    code = "NOT-01"
    http_status = 404


class OverlappingVersionsError(RulesError):
    """Deux versions publiées couvrent la même date : la décision ne serait pas rejouable."""

    code = "RUL-02"
    http_status = 409


class InvalidRuleParamsError(RulesError):
    """Paramètres d'une version de règle absents, en trop ou mal typés."""

    code = "VAL-01"
    http_status = 422


class PublishedVersionFrozenError(RulesError):
    """Version déjà publiée : elle ne change plus et ne se republie pas."""

    code = "RUL-01"
    http_status = 409


class InvalidRequestError(RulesError):
    """Demande incohérente (période inversée, garantie en double…)."""

    code = "VAL-01"
    http_status = 422


class DuplicateCodeError(RulesError):
    """Code déjà utilisé dans l'organisation (409 ; code VAL-01, même choix que L1/CR-L1-01)."""

    code = "VAL-01"
    http_status = 409
