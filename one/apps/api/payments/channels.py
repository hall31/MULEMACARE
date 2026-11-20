"""Canaux de paiement derrière une interface ; implémentations SIMULÉES uniquement (PRD §10 Q1).

Aucune intégration réelle Wave / Orange Money / MTN MoMo tant que l'accès API n'est pas tranché :
``SimulatedChannel`` n'ouvre aucune connexion réseau (prouvé sous la garde d'egress dans les
tests). Un adaptateur réel implémentera ``PaymentChannel`` (vérification de signature propre au
canal, démarrage du paiement) et traduira la notification du canal vers le format normalisé
``PaymentWebhookRequest`` du contrat.

Signature des notifications simulées : ``X-Signature`` = HMAC-SHA256 hexadécimal du corps brut,
avec un secret PAR CANAL fourni par l'exploitation (jamais dans le code ni les tests).
Aucun numéro de carte bancaire n'existe dans ce flux : le payeur paie chez le canal.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, Protocol, runtime_checkable
from uuid import UUID

from api.members.outbox import rfc3339

type ChannelName = Literal[
    "wave", "orange_money", "mtn_momo", "virement", "prelevement_employeur", "simulation"
]

SIMULATED_CHANNELS: Final = ("wave", "orange_money", "mtn_momo")
_MIN_SECRET_BYTES: Final = 32


@dataclass(frozen=True, slots=True)
class CheckoutOrder:
    payment_id: UUID
    amount_xof: int
    currency: str = "XOF"


@dataclass(frozen=True, slots=True)
class CheckoutStarted:
    provider_reference: str
    redirect_url: str | None


@runtime_checkable
class PaymentChannel(Protocol):
    @property
    def name(self) -> str: ...

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        """Vrai seulement si la signature du corps brut est celle du canal."""
        ...

    async def start_checkout(self, order: CheckoutOrder) -> CheckoutStarted:
        """Démarre le paiement chez le canal ; renvoie sa référence."""
        ...


@dataclass(frozen=True, slots=True)
class SignedNotification:
    event_id: str
    body: bytes
    signature: str


class SimulatedChannel:
    """Canal SIMULÉ : en mémoire, sans réseau. Sert au développement et aux tests."""

    def __init__(self, name: str, secret: bytes) -> None:
        if name not in SIMULATED_CHANNELS:
            msg = f"canal simulé inconnu : {name!r}"
            raise ValueError(msg)
        if len(secret) < _MIN_SECRET_BYTES:
            msg = "secret de signature trop court (32 octets minimum)"
            raise ValueError(msg)
        self._name = name
        self._secret = secret
        self._started: dict[UUID, tuple[str, int]] = {}

    @property
    def name(self) -> str:
        return self._name

    def sign(self, body: bytes) -> str:
        return hmac.new(self._secret, body, hashlib.sha256).hexdigest()

    def verify_signature(self, body: bytes, signature: str | None) -> bool:
        if not signature:
            return False
        return hmac.compare_digest(self.sign(body), signature.strip().lower())

    async def start_checkout(self, order: CheckoutOrder) -> CheckoutStarted:
        reference = f"SIM-{self._name.upper()}-{uuid.uuid4().hex[:20].upper()}"
        self._started[order.payment_id] = (reference, order.amount_xof)
        return CheckoutStarted(provider_reference=reference, redirect_url=None)

    def notification(
        self,
        payment_id: UUID,
        *,
        occurred_at: datetime,
        status: Literal["confirme", "echoue"] = "confirme",
        amount_xof: int | None = None,
        event_id: str | None = None,
    ) -> SignedNotification:
        """Notification signée que le canal enverrait pour un paiement démarré (simulation)."""
        reference, amount = self._started[payment_id]
        event = event_id or f"evt-{self._name}-{uuid.uuid4().hex}"
        body = json.dumps(
            {
                "event_id": event,
                "provider_reference": reference,
                "merchant_reference": str(payment_id),
                "status": status,
                "amount_xof": amount if amount_xof is None else amount_xof,
                "currency": "XOF",
                "occurred_at": rfc3339(occurred_at),
            }
        ).encode()
        return SignedNotification(event_id=event, body=body, signature=self.sign(body))


class ChannelRegistry:
    """Canaux activés pour l'instance ; un canal absent est refusé (404 / 422)."""

    def __init__(self, channels: Iterable[PaymentChannel]) -> None:
        self._channels: dict[str, PaymentChannel] = {}
        for channel in channels:
            if channel.name in self._channels:
                msg = f"canal en double : {channel.name}"
                raise ValueError(msg)
            self._channels[channel.name] = channel

    def get(self, name: str) -> PaymentChannel | None:
        return self._channels.get(name)

    def names(self) -> list[str]:
        return sorted(self._channels)
