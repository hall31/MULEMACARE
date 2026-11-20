"""Configuration des paiements, lue dans l'environnement (aucun secret dans le code).

- ``MULEMA_PAYMENT_LINK_SECRET`` : clé (hex, 32 octets min.) qui dérive les jetons de lien ;
- ``MULEMA_PAYMENT_PUBLIC_BASE_URL`` : base des liens publics (page du payeur) ;
- ``MULEMA_PAYMENT_SECRET_<CANAL>`` (WAVE, ORANGE_MONEY, MTN_MOMO) : secret de signature des
  notifications ; un canal sans secret n'est pas activé.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from api.payments.channels import SIMULATED_CHANNELS, ChannelRegistry, SimulatedChannel

# Défauts techniques non fixés par le PRD (specs/QUESTIONS.md, Q-L4-06).
DEFAULT_LINK_TTL: Final = timedelta(days=7)
DEFAULT_WEBHOOK_KEY_TTL: Final = timedelta(days=30)
_MIN_SECRET_BYTES: Final = 32


@dataclass(frozen=True, slots=True)
class PaymentsConfig:
    link_secret: bytes
    public_base_url: str
    channels: ChannelRegistry
    link_ttl: timedelta = DEFAULT_LINK_TTL
    webhook_key_ttl: timedelta = DEFAULT_WEBHOOK_KEY_TTL

    def __post_init__(self) -> None:
        if len(self.link_secret) < _MIN_SECRET_BYTES:
            msg = "MULEMA_PAYMENT_LINK_SECRET trop court (32 octets minimum)"
            raise ValueError(msg)
        if not self.public_base_url.startswith("https://"):
            msg = "MULEMA_PAYMENT_PUBLIC_BASE_URL doit être une URL https"
            raise ValueError(msg)

    @classmethod
    def from_env(cls) -> PaymentsConfig:
        link_secret = os.environ.get("MULEMA_PAYMENT_LINK_SECRET")
        base_url = os.environ.get("MULEMA_PAYMENT_PUBLIC_BASE_URL")
        if not link_secret or not base_url:
            msg = "MULEMA_PAYMENT_LINK_SECRET et MULEMA_PAYMENT_PUBLIC_BASE_URL sont requis"
            raise RuntimeError(msg)
        channels = []
        for name in SIMULATED_CHANNELS:
            secret = os.environ.get(f"MULEMA_PAYMENT_SECRET_{name.upper()}")
            if secret:
                channels.append(SimulatedChannel(name, bytes.fromhex(secret)))
        return cls(
            link_secret=bytes.fromhex(link_secret),
            public_base_url=base_url.rstrip("/"),
            channels=ChannelRegistry(channels),
        )
