"""Erreurs typées de la marque blanche (P3, CR-P3-01), codes stables du contrat."""

from __future__ import annotations

from api.core.errors import DomainError, ErrorCode


class BrandContrastError(DomainError):
    code = ErrorCode.BRD_01
    status_code = 422
    default_message = "Ces couleurs ne sont pas assez lisibles (contraste WCAG AA)."
    default_action = "Choisissez une couleur plus foncée en clair ou plus claire en sombre."


class BrandTokenError(DomainError):
    code = ErrorCode.BRD_02
    status_code = 422
    default_message = "Seuls quelques jetons de couleur se personnalisent, au format #RRGGBB."
    default_action = "Retirez les jetons signalés ou corrigez leur couleur."


class BrandLogoError(DomainError):
    code = ErrorCode.BRD_03
    status_code = 422
    default_message = "Ce logo est refusé : il pourrait s'exécuter ou venir d'un site non autorisé."
    default_action = "Envoyez une image PNG, WebP, JPEG ou un SVG simple de 32 Ko au plus."


class BrandDomainReservedError(DomainError):
    code = ErrorCode.BRD_05
    status_code = 422
    default_message = "Ce domaine est réservé : il ne peut pas être celui d'une organisation."
    default_action = "Déclarez un domaine que votre organisation possède (ex. sante.votre-nom.ci)."


class BrandDomainUnverifiedError(DomainError):
    code = ErrorCode.BRD_06
    status_code = 422
    default_message = "La propriété du domaine n'est pas prouvée."
    default_action = (
        "Publiez l'enregistrement DNS TXT indiqué dans les réglages, attendez sa propagation, "
        "puis relancez la vérification."
    )


class BrandDomainTakenError(DomainError):
    code = ErrorCode.BRD_04
    status_code = 409
    default_message = "Ce domaine est déjà déclaré par une autre organisation."
    default_action = "Vérifiez le domaine ou contactez l'équipe de la plateforme."
