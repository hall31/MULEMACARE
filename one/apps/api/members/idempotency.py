"""Clés d'idempotence stockées (table ``idempotency_keys`` du contrat) pour le lot L4.

La clé est réservée DANS la transaction de la commande : si la commande échoue, la réservation
disparaît avec elle ; si elle réussit, la clé pointe vers la ressource produite (identifiant
seulement : aucune donnée identifiante, aucun jeton n'est recopié dans ``response_body``).

Concurrence : deux transactions qui insèrent la même clé se sérialisent sur l'index unique ;
la seconde attend le COMMIT de la première, puis lit la réponse enregistrée (rejeu) ou, si la
première a été annulée, prend la clé à son tour.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.members.errors import idempotency_in_progress, idempotency_mismatch

_SCOPE: Final = re.compile(r"^[a-z_]+:[a-z_.]+$")
KEY_MIN, KEY_MAX = 8, 200

# Durée de conservation : défaut technique non fixé par les contrats (QUESTIONS.md, Q-L4-06).
COMMAND_KEY_TTL: Final = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status: int
    body: dict[str, Any]


@dataclass(frozen=True, slots=True)
class KeyRequest:
    """Clé fournie par l'appelant, dans sa portée, avec l'empreinte de la demande."""

    scope: str
    key: str
    request_hash: str

    def __post_init__(self) -> None:
        if not _SCOPE.fullmatch(self.scope):
            msg = f"portée d'idempotence invalide : {self.scope!r}"
            raise ValueError(msg)
        if not KEY_MIN <= len(self.key) <= KEY_MAX:
            msg = "clé d'idempotence hors bornes (8 à 200 caractères)"
            raise ValueError(msg)


def fingerprint(value: object) -> str:
    """Empreinte stable d'une demande (JSON canonique, SHA-256)."""
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class IdempotencyStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def begin(
        self,
        organization_id: UUID,
        request: KeyRequest,
        *,
        now: datetime,
        ttl: timedelta = COMMAND_KEY_TTL,
    ) -> StoredResponse | None:
        """Réserve la clé. Renvoie la réponse déjà produite, ou ``None`` si la clé est neuve."""
        scope, key, request_hash = request.scope, request.key, request.request_hash
        params = {"org": organization_id, "scope": scope, "key": key}
        await self._session.execute(
            text(
                "DELETE FROM idempotency_keys WHERE organization_id = :org AND scope = :scope "
                "AND key = :key AND expires_at <= :now"
            ),
            {**params, "now": now},
        )
        inserted = (
            await self._session.execute(
                text(
                    "INSERT INTO idempotency_keys (organization_id, scope, key, request_hash, "
                    "created_at, expires_at) VALUES (:org, :scope, :key, :hash, :now, :expires) "
                    "ON CONFLICT (organization_id, scope, key) DO NOTHING RETURNING key"
                ),
                {**params, "hash": request_hash, "now": now, "expires": now + ttl},
            )
        ).first()
        if inserted is not None:
            return None
        row = (
            await self._session.execute(
                text(
                    "SELECT request_hash, status, response_status, response_body "
                    "FROM idempotency_keys "
                    "WHERE organization_id = :org AND scope = :scope AND key = :key"
                ),
                params,
            )
        ).first()
        if row is None:  # conflit d'insertion => la ligne existe ; défense seulement
            raise idempotency_in_progress()
        stored_hash, state, response_status, body = row
        if stored_hash != request_hash:
            raise idempotency_mismatch()
        if state != "terminee" or not isinstance(body, dict) or response_status is None:
            raise idempotency_in_progress()
        return StoredResponse(int(str(response_status)), body)

    async def complete(
        self, organization_id: UUID, request: KeyRequest, status: int, body: dict[str, Any]
    ) -> None:
        await self._session.execute(
            text(
                "UPDATE idempotency_keys SET status = 'terminee', response_status = :status, "
                "response_body = CAST(:body AS jsonb) "
                "WHERE organization_id = :org AND scope = :scope AND key = :key"
            ),
            {
                "status": status,
                "body": json.dumps(body),
                "org": organization_id,
                "scope": request.scope,
                "key": request.key,
            },
        )
