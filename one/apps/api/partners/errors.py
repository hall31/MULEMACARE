"""Erreurs typées de l'accueil d'organisation (P3, CR-P3-01), codes stables du contrat."""

from __future__ import annotations

from api.core.errors import DomainError, ErrorCode


class OrganizationSlugTakenError(DomainError):
    code = ErrorCode.ORG_01
    status_code = 409
    default_message = "Cet identifiant public d'organisation est déjà utilisé."
    default_action = "Choisissez un autre identifiant (lettres minuscules, chiffres, tirets)."


class TemplateUnavailableError(DomainError):
    code = ErrorCode.ORG_02
    status_code = 422
    default_message = "Ce gabarit de configuration est introuvable ou prévu pour un autre pays."
    default_action = "Choisissez un gabarit du même pays dans la liste des gabarits."
