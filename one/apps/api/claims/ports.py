"""Ports du lot L5 : ce que le module attend de l'extérieur, injecté par ``install(app, runtime)``.

Aucune implémentation « par défaut » silencieuse pour la production : le QR dynamique (format
porté par l'émission de carte, L4) et le fournisseur SMS ne sont pas choisis (QUESTIONS.md,
Q-L5-01, apps/api/claims/QUESTIONS.md). Le fournisseur SMS simulé n'envoie rien sur le réseau.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.clock import Clock, SystemClock
from api.integrations.healthos import HealthOSClient


class QrVerifier(Protocol):
    """Vérifie un QR dynamique de carte et renvoie la carte désignée (ou ``None``).

    Reçoit la transaction de la requête et l'organisation du jeton : le vérificateur réel
    (``api.members.cards.verify_qr_payload``, L4) lit le secret scellé de la carte en base.
    """

    async def resolve(
        self, qr_payload: str, *, at: datetime, session: AsyncSession, organization_id: UUID
    ) -> UUID | None: ...


class SmsSender(Protocol):
    """Envoie un code à usage unique. Le code n'est jamais stocké ni journalisé par L5."""

    async def send_code(self, *, phone_e164: str, code: str) -> None: ...


class FraudScorer(Protocol):
    """Score de fraude entre 0 et 1, ou ``None`` si inconnu (alors revue, Q-L2-05)."""

    async def score(self, *, member_id: UUID, provider_id: UUID) -> Decimal | None: ...


class NoFraudScore:
    """Défaut tant que Q-L0-05 n'est pas tranchée : aucun score, donc aucun accord auto."""

    async def score(self, *, member_id: UUID, provider_id: UUID) -> Decimal | None:
        del member_id, provider_id
        return None


@dataclass(frozen=True, slots=True)
class SentSms:
    phone_e164: str
    code: str


@dataclass(slots=True)
class SimulatedSmsSender:
    """Fournisseur SMS simulé (PRD §2, aucun envoi réel) : garde les messages en mémoire."""

    sent: list[SentSms] = field(default_factory=list)

    async def send_code(self, *, phone_e164: str, code: str) -> None:
        self.sent.append(SentSms(phone_e164, code))

    def last_code(self, phone_e164: str) -> str:
        for message in reversed(self.sent):
            if message.phone_e164 == phone_e164:
                return message.code
        msg = "aucun code envoyé à ce numéro"
        raise LookupError(msg)


# Durée de validité du code SMS : non fixée par le contrat (Q-L0-06) ; défaut à valider.
DEFAULT_SMS_CODE_VALIDITY = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class ClaimsRuntime:
    healthos: HealthOSClient
    qr_verifier: QrVerifier
    sms_sender: SmsSender
    fraud_scorer: FraudScorer = field(default_factory=NoFraudScore)
    clock: Clock = field(default_factory=SystemClock)
    sms_code_validity: timedelta = DEFAULT_SMS_CODE_VALIDITY
