"""Table de correspondance VERSIONNÉE des statuts de l'existant vers One.

Quatre vocabulaires d'adhésion/dossier coexistent dans l'existant (PRD §10) :
- ``laravel_legacy`` : ``subscription_aderents.status`` (enum de 2025, en français) et
  ``demande_remboursements.status`` ;
- ``laravel_2026`` : ``mutual_subscriptions.status`` (constantes de ``MutualSubscription``) et
  ``claims.status`` ;
- ``site_php`` : ``mulema_subscribers.status``, ``mulema_claims.status`` (dump du site) ;
- paiements : ``payments.status`` (Laravel) et ``mulema_payments.status`` (site).

Chaque valeur est soit TRADUITE (``Mapped``), soit EXCLUE avec un motif (``Excluded``) ; une
valeur absente de la table est REJETÉE (REJ-01). Il n'y a pas de valeur par défaut. Comparaison
exacte (casse et accents compris) après suppression des espaces de bord.

Adhérents : le statut d'import est un statut de REVUE HUMAINE (``external_ids.import_status``).
Dans One, tout adhérent importé a ses droits FERMÉS (``members.status = 'suspendu'``) : Laravel
reste maître jusqu'à la bascule de sa cohorte (ADR-001, R16) ; un adhérent actif dans la source
arrive en ``PENDING_REVIEW``.

Dossiers : seuls les dossiers CLOS sont importés ; un dossier en cours reste traité par Laravel
(sinon il apparaîtrait dans la file du médecin-conseil de One et pourrait être décidé deux fois).

Changer une ligne = nouvelle ``STATUS_MAP_VERSION`` (enregistrée dans ``import_runs`` et
``external_ids``) + validation humaine (PRD §10, specs/QUESTIONS.md Q-L11-xx).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from api.legacy_import.errors import RowRejectedError

STATUS_MAP_VERSION: Final = "statuts-2026-10-02.1"


@dataclass(frozen=True, slots=True)
class Mapped:
    """Valeur de One (ou statut d'import) correspondant à la valeur de la source."""

    value: str


@dataclass(frozen=True, slots=True)
class Excluded:
    """Ligne volontairement hors import ; ``code`` stable (EXC-xx) et motif lisible."""

    code: str
    reason: str


type StatusOutcome = Mapped | Excluded

# Statuts d'import d'un adhérent (revue humaine) ; droits fermés dans One pour tous.
PENDING_REVIEW: Final = Mapped("PENDING_REVIEW")
AWAITING_PAYMENT: Final = Mapped("AWAITING_PAYMENT")
SUSPENDED: Final = Mapped("SUSPENDED")
EXPIRED: Final = Mapped("EXPIRED")
TERMINATED: Final = Mapped("TERMINATED")
IMPORTED_MEMBER_STATUS: Final = "suspendu"

DRAFT = Excluded("EXC-01", "Brouillon : jamais soumis, ce n'est pas un dossier.")
IN_PROGRESS = Excluded("EXC-02", "Dossier en cours : reste traité par Laravel jusqu'à la bascule.")
NOT_RECEIVED = Excluded("EXC-03", "Paiement non abouti : aucune cotisation reçue.")
REFUNDED = Excluded("EXC-04", "Paiement remboursé : aucune cotisation acquise.")

STATUS_MAP: Final[Mapping[str, Mapping[str, StatusOutcome]]] = {
    # --- adhésions → statut d'import (revue humaine) ---------------------------------------
    "laravel_legacy.subscription": {
        "Attente de paiement": AWAITING_PAYMENT,
        "Activé": PENDING_REVIEW,
        "Expiré": EXPIRED,
        "Terminé": TERMINATED,
    },
    "laravel_2026.subscription": {
        "pending_payment": AWAITING_PAYMENT,
        "active": PENDING_REVIEW,
        "suspended": SUSPENDED,
        "expired": EXPIRED,
        "terminated": TERMINATED,
    },
    "site_php.subscriber": {
        "active": PENDING_REVIEW,
        "pending": AWAITING_PAYMENT,
        "suspended": SUSPENDED,
        "cancelled": TERMINATED,
    },
    # --- dossiers → claims.status de One (dossiers clos seulement) --------------------------
    "laravel_legacy.claim": {
        "en attente": IN_PROGRESS,
        "approuvé": Mapped("accordee"),
        "rejeté": Mapped("refusee"),
        "payé": Mapped("payee"),
    },
    "laravel_2026.claim": {
        "draft": DRAFT,
        "submitted": IN_PROGRESS,
        "pending_review": IN_PROGRESS,
        "approved": Mapped("accordee"),
        "rejected": Mapped("refusee"),
        "paid": Mapped("payee"),
    },
    "site_php.claim": {
        "pending_approval": IN_PROGRESS,
        "approved": Mapped("accordee"),
        "rejected": Mapped("refusee"),
        "reimbursed_to_clinic": Mapped("payee"),
    },
    # --- paiements → contributions (seul un paiement abouti est une cotisation reçue) -------
    "laravel.payment": {
        "réussi": Mapped("payee"),
        "en attente": NOT_RECEIVED,
        "échoué": NOT_RECEIVED,
        "remboursé": REFUNDED,
    },
    "site_php.payment": {
        "succeeded": Mapped("payee"),
        "pending": NOT_RECEIVED,
        "failed": NOT_RECEIVED,
    },
}

# --- Mode ombre (L12) : faits et décisions de la source à la date du soin ------------------

# Statut d'adhésion de la source à la date du soin → statut de One lu par R-01.
RIGHTS_AT_SERVICE_DATE: Final[Mapping[str, Mapping[str, StatusOutcome]]] = {
    "laravel_legacy.subscription": {
        "Attente de paiement": Mapped("suspendu"),
        "Activé": Mapped("actif"),
        "Expiré": Mapped("suspendu"),
        "Terminé": Mapped("suspendu"),
    },
    "laravel_2026.subscription": {
        "pending_payment": Mapped("suspendu"),
        "active": Mapped("actif"),
        "suspended": Mapped("suspendu"),
        "expired": Mapped("suspendu"),
        "terminated": Mapped("suspendu"),
    },
    "site_php.subscriber": {
        "active": Mapped("actif"),
        "pending": Mapped("suspendu"),
        "suspended": Mapped("suspendu"),
        "cancelled": Mapped("suspendu"),
    },
}

# Décision historique de la source → classe comparable : accord, refus, revue.
DECISIONS: Final[Mapping[str, Mapping[str, StatusOutcome]]] = {
    "laravel_legacy.claim": {
        "en attente": Mapped("revue"),
        "approuvé": Mapped("accord"),
        "payé": Mapped("accord"),
        "rejeté": Mapped("refus"),
    },
    "laravel_2026.claim": {
        "draft": DRAFT,
        "submitted": Mapped("revue"),
        "pending_review": Mapped("revue"),
        "approved": Mapped("accord"),
        "paid": Mapped("accord"),
        "rejected": Mapped("refus"),
    },
    "site_php.claim": {
        "pending_approval": Mapped("revue"),
        "approved": Mapped("accord"),
        "reimbursed_to_clinic": Mapped("accord"),
        "rejected": Mapped("refus"),
    },
}


def lookup(
    table: Mapping[str, Mapping[str, StatusOutcome]], vocabulary: str, raw: object, field: str
) -> StatusOutcome:
    """Traduit ``raw`` ; vocabulaire ou valeur inconnus → REJ-01 (jamais de défaut)."""
    values = table.get(vocabulary)
    if values is None:
        msg = f"vocabulaire de statuts inconnu : {vocabulary}"
        raise LookupError(msg)
    value = "" if raw is None else str(raw).strip()
    outcome = values.get(value)
    if outcome is None:
        raise RowRejectedError("REJ-01", field)
    return outcome
