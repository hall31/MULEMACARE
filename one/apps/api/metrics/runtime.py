"""Dépendances du module de mesure : horloge, clé de pseudonymisation, rétention.

- ``MULEMA_METRICS_PSEUDONYM_KEY`` (OBLIGATOIRE, hexadécimal, 32 octets au moins) : clé HMAC qui
  dérive l'empreinte d'une personne (``catalog.person_ref``). Elle vit dans la configuration du
  serveur (gestionnaire de secrets), jamais en base ni dans le dépôt : sans elle, une empreinte
  ne se relie à aucun utilisateur, même avec une copie complète de la base.
- ``MULEMA_METRICS_PSEUDONYM_KEY_SINCE`` (facultatif, date ISO) : jour de la dernière rotation.
  Tourner la clé change toutes les empreintes : une personne active des deux côtés compterait
  deux fois. Les indicateurs d'usage ne comptent donc que les semaines qui commencent
  STRICTEMENT après ce jour (``windows.key_floor``). Procédure : générer une clé neuve
  (``python -c "import secrets; print(secrets.token_hex(32))"``), la poser avec la date du
  jour dans ``…_SINCE``, redémarrer ; l'ancienne clé est détruite (rien ne la réutilise).
- ``MULEMA_PRODUCT_EVENTS_RETENTION_DAYS`` : rétention des événements (180 jours par défaut).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Final

from api.core.clock import Clock

KEY_ENV: Final = "MULEMA_METRICS_PSEUDONYM_KEY"
KEY_SINCE_ENV: Final = "MULEMA_METRICS_PSEUDONYM_KEY_SINCE"
RETENTION_ENV: Final = "MULEMA_PRODUCT_EVENTS_RETENTION_DAYS"
MIN_KEY_BYTES: Final = 32
# Défaut à valider (Q-P2-02) : six mois, assez pour une tendance trimestrielle.
DEFAULT_RETENTION_DAYS: Final = 180
MIN_RETENTION_DAYS: Final = 1
MAX_RETENTION_DAYS: Final = 730


@dataclass(frozen=True, slots=True)
class MetricsRuntime:
    """``retention_days`` : durée de conservation d'un événement, posée à l'insertion.

    ``pseudonym_key`` n'apparaît dans aucune représentation (journaux, traces d'erreur).
    """

    clock: Clock
    pseudonym_key: bytes = field(repr=False)
    retention_days: int = DEFAULT_RETENTION_DAYS
    pseudonym_key_since: date | None = None

    def __post_init__(self) -> None:
        if len(self.pseudonym_key) < MIN_KEY_BYTES:
            msg = f"{KEY_ENV} trop courte ({MIN_KEY_BYTES} octets minimum)"
            raise ValueError(msg)
        if not MIN_RETENTION_DAYS <= self.retention_days <= MAX_RETENTION_DAYS:
            msg = (
                f"rétention des événements hors bornes ({MIN_RETENTION_DAYS} à "
                f"{MAX_RETENTION_DAYS} jours) : {self.retention_days}"
            )
            raise ValueError(msg)

    @classmethod
    def from_env(cls, clock: Clock, env: Mapping[str, str]) -> MetricsRuntime:
        raw_key = env.get(KEY_ENV)
        if not raw_key:
            msg = f"{KEY_ENV} manquante : clé de pseudonymisation de la mesure (hexadécimal)"
            raise ValueError(msg)
        try:
            key = bytes.fromhex(raw_key)
        except ValueError:
            msg = f"{KEY_ENV} doit être en hexadécimal"
            raise ValueError(msg) from None
        if len(key) < MIN_KEY_BYTES:
            msg = f"{KEY_ENV} trop courte ({MIN_KEY_BYTES} octets minimum)"
            raise ValueError(msg)
        since = None
        if raw_since := env.get(KEY_SINCE_ENV):
            try:
                since = date.fromisoformat(raw_since)
            except ValueError:
                msg = f"{KEY_SINCE_ENV} doit être une date ISO (AAAA-MM-JJ)"
                raise ValueError(msg) from None
        days = DEFAULT_RETENTION_DAYS
        if raw_days := env.get(RETENTION_ENV):
            try:
                days = int(raw_days)
            except ValueError:
                msg = f"{RETENTION_ENV} doit être un nombre entier de jours"
                raise ValueError(msg) from None
        return cls(clock=clock, pseudonym_key=key, retention_days=days, pseudonym_key_since=since)
