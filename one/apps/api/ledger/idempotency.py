"""Clés d'idempotence des commandes du grand livre (table ``idempotency_keys`` du contrat).

La clé est réservée dans la transaction de la commande : si la commande échoue, la réservation
disparaît avec elle ; si elle réussit, la clé pointe vers l'écriture créée.
"""

from __future__ import annotations

import json
from typing import Final
from uuid import UUID

from api.ledger.domain import LedgerError
from api.ledger.repository import Conn

# Durée de conservation d'une clé : défaut technique non fixé par les contrats (à valider).
KEY_TTL: Final = "24 hours"


async def begin(
    conn: Conn, organization_id: UUID, scope: str, key: str, request_hash: str
) -> UUID | None:
    """Réserve la clé. Renvoie l'écriture déjà produite par cette clé, ou ``None`` si neuve."""
    await conn.execute(
        "DELETE FROM idempotency_keys WHERE organization_id = %s AND scope = %s AND key = %s "
        "AND expires_at <= now()",
        (organization_id, scope, key),
    )
    cur = await conn.execute(
        "INSERT INTO idempotency_keys (organization_id, scope, key, request_hash, expires_at) "
        "VALUES (%s, %s, %s, %s, now() + %s::interval) "
        "ON CONFLICT (organization_id, scope, key) DO NOTHING RETURNING key",
        (organization_id, scope, key, request_hash, KEY_TTL),
    )
    if await cur.fetchone() is not None:
        return None
    cur = await conn.execute(
        "SELECT request_hash, status, response_body FROM idempotency_keys "
        "WHERE organization_id = %s AND scope = %s AND key = %s",
        (organization_id, scope, key),
    )
    row = await cur.fetchone()
    if row is None:  # conflit => la ligne existe (verrou de journal tenu)
        raise RuntimeError("clé d'idempotence en conflit mais introuvable")
    stored_hash, status, body = row
    if stored_hash != request_hash:
        raise LedgerError(
            "IDEM-01",
            "Cette clé d'idempotence a déjà servi pour une autre demande.",
            "Générez une nouvelle clé pour une nouvelle demande.",
        )
    if status != "terminee" or not isinstance(body, dict) or "entry_id" not in body:
        raise LedgerError(
            "IDEM-02",
            "Cette demande est déjà en cours de traitement.",
            "Patientez quelques secondes puis rechargez l'écriture.",
        )
    return UUID(str(body["entry_id"]))


async def complete(conn: Conn, organization_id: UUID, scope: str, key: str, entry_id: UUID) -> None:
    await conn.execute(
        "UPDATE idempotency_keys SET status = 'terminee', response_status = 201, "
        "response_body = %s WHERE organization_id = %s AND scope = %s AND key = %s",
        (json.dumps({"entry_id": str(entry_id)}), organization_id, scope, key),
    )
