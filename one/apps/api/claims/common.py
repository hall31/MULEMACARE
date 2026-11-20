"""Aides communes du lot L5 : portée d'accès, date locale, empreinte du code SMS."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
from datetime import date, datetime
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from api.claims.errors import ClaimsError, invalid, not_found
from api.core.context import RequestContext
from api.core.permissions import AccessScope, ResourceScope

_PBKDF2_ITERATIONS: Final = 20_000
CODE_DIGITS: Final = 6


def access(ctx: RequestContext) -> AccessScope:
    if ctx.access is None:  # require_operation la renseigne toujours
        msg = "portée d'accès absente : route montée sans require_operation"
        raise RuntimeError(msg)
    return ctx.access


def ensure_in_scope(ctx: RequestContext, provider_id: UUID) -> None:
    """Hors périmètre = introuvable (on ne dit pas pourquoi)."""
    if not access(ctx).allows(ResourceScope(provider_id=provider_id)):
        raise not_found()


def clinic_provider(ctx: RequestContext) -> UUID:
    """Établissement de la clinique ; plusieurs établissements = ambigu (VAL-01)."""
    scope = access(ctx)
    if len(scope.provider_ids) != 1:
        raise invalid(
            "Votre compte est rattaché à plusieurs établissements (ou à aucun).",
            "Demandez à l'administrateur un compte par établissement.",
        )
    return next(iter(scope.provider_ids))


def local_date(moment: datetime, timezone: str) -> date:
    return moment.astimezone(ZoneInfo(timezone)).date()


def seconds_until(later: datetime, now: datetime) -> int:
    return max(math.ceil((later - now).total_seconds()), 0)


def new_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def hash_code(code: str, salt: bytes | None = None) -> str:
    """Empreinte salée du code (le code n'est jamais stocké en clair)."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode(), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def code_matches(code: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", code.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def request_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def idempotency_conflict() -> ClaimsError:
    return ClaimsError(
        "IDEM-01",
        409,
        "Cette clé d'idempotence a déjà servi pour une autre demande.",
        "Générez une nouvelle clé pour une nouvelle demande.",
    )


def idempotency_in_progress() -> ClaimsError:
    return ClaimsError(
        "IDEM-02",
        409,
        "Cette demande est déjà en cours de traitement.",
        "Patientez quelques secondes puis rechargez le dossier.",
    )
