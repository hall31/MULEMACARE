"""Jetons des liens de paiement : dérivés par HMAC, seul leur hachage est stocké.

``jeton = base64url(HMAC-SHA256(clé de l'application, "payment-link:" || id du lien))``.
La base ne garde que ``sha256(jeton)`` (``payment_links.token_hash``) : une copie de la base ne
suffit pas à payer à la place du payeur, ni à retrouver un lien. Le serveur peut recalculer le
jeton d'un lien qu'il connaît (rejeu idempotent de ``createPaymentLink``, relance par SMS) sans
jamais le stocker.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from uuid import UUID


def token_for(link_secret: bytes, link_id: UUID) -> str:
    digest = hmac.new(link_secret, b"payment-link:" + link_id.bytes, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def initials(given_name: str, family_name: str) -> str:
    """« A. K. » : initiales seulement, jamais le nom (page publique du payeur)."""
    parts = [p[:1].upper() + "." for p in (given_name.strip(), family_name.strip()) if p]
    return " ".join(parts)
