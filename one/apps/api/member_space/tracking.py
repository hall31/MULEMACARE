"""Frise d'un remboursement (P1) : quatre étapes déduites du statut et du journal des décisions.

Étapes : ``demande_recue``, ``accordee`` (décision de la mutuelle), ``virement``, ``recu``. Les
codes sont stables ; les libellés vivent dans les fichiers de traduction de l'interface.
Seuls sortent le code public de la règle (``R-12`` v3) ou le code de motif d'une décision
humaine (``MC-02``) : jamais de trace d'évaluation, de score ni d'identifiant interne.

Le contrat ne date ni le virement ni sa réception (aucune colonne, QUESTIONS Q-P1-03) : ``at``
reste nul pour ces deux étapes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

type StepKey = Literal["demande_recue", "accordee", "virement", "recu"]
type StepState = Literal["fait", "en_cours", "a_venir", "refuse", "annule", "sans_objet"]

STEP_KEYS: Final[tuple[StepKey, ...]] = ("demande_recue", "accordee", "virement", "recu")

GRANTED: Final = frozenset({"accordee_auto", "accordee"})
PENDING: Final = frozenset({"demandee", "en_revue", "pieces_demandees"})
# Statut du dossier → état des étapes « accordée », « virement », « reçu ».
_STATES: Final[dict[str, tuple[StepState, StepState, StepState]]] = {
    "demandee": ("en_cours", "a_venir", "a_venir"),
    "en_revue": ("en_cours", "a_venir", "a_venir"),
    "pieces_demandees": ("en_cours", "a_venir", "a_venir"),
    "accordee_auto": ("fait", "en_cours", "a_venir"),
    "accordee": ("fait", "en_cours", "a_venir"),
    "payee": ("fait", "fait", "fait"),
    "refusee": ("refuse", "sans_objet", "sans_objet"),
    "annulee": ("annule", "sans_objet", "sans_objet"),
}
# Décision qui date l'étape « accordée » selon le statut du dossier.
_DECIDING: Final[dict[str, frozenset[str]]] = {
    "accordee_auto": GRANTED,
    "accordee": GRANTED,
    "payee": GRANTED,
    "refusee": frozenset({"refusee"}),
    "annulee": frozenset({"annulee"}),
    "en_revue": frozenset({"en_revue"}),
    "pieces_demandees": frozenset({"pieces_demandees", "en_revue"}),
    "demandee": frozenset(),
}


@dataclass(frozen=True, slots=True)
class DecisionView:
    """Ligne du journal ``claim_decisions`` réduite à ce qui est public."""

    outcome: str
    rule_code: str | None
    rule_version: int | None
    reason_code: str
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class Step:
    key: StepKey
    state: StepState
    at: datetime | None = None
    rule_code: str | None = None
    rule_version: int | None = None
    reason_code: str | None = None


def tracking_steps(
    status: str, requested_at: datetime, decisions: Sequence[DecisionView]
) -> list[Step]:
    """Quatre étapes, dans l'ordre de ``STEP_KEYS``. Statut inconnu : ``ValueError``."""
    try:
        decision_state, transfer_state, received_state = _STATES[status]
    except KeyError:
        msg = f"statut de dossier inconnu : {status!r}"
        raise ValueError(msg) from None
    deciding = [d for d in decisions if d.outcome in _DECIDING[status]]
    last = deciding[-1] if deciding else None
    decision = Step(
        "accordee",
        decision_state,
        at=last.decided_at if last else None,
        rule_code=last.rule_code if last else None,
        rule_version=last.rule_version if last else None,
        reason_code=last.reason_code if last else None,
    )
    return [
        Step("demande_recue", "fait", at=requested_at),
        decision,
        Step("virement", transfer_state),
        Step("recu", received_state),
    ]
