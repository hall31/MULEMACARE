"""Aides des tests L5 : signataire ES256 de test, validateur des événements, horloge, QR.

Tout est fictif. Le signataire reproduit le format du comptoir (L7, Q-L7-03) : JSON canonique
(clés triées, sans espace, UTF-8), ``signed_payload`` = base64url de ces octets, ``signature`` =
base64url des 64 octets r‖s.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from api.claims import ecdsa
from api.tests.paths import EVENTS_MD

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class MutableClock:
    """Horloge de test pilotable (UTC)."""

    def __init__(self, start: datetime = T0) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeQrVerifier:
    """QR dynamique de TEST : une charge utile connue désigne une carte."""

    def __init__(self) -> None:
        self.cards: dict[str, UUID] = {}

    async def resolve(
        self, qr_payload: str, *, at: datetime, session: object, organization_id: UUID
    ) -> UUID | None:
        del at, session, organization_id
        return self.cards.get(qr_payload)


@dataclass
class ScriptedFraudScorer:
    """Score de fraude fixé par le test (le fournisseur réel n'est pas choisi, Q-L0-05)."""

    value: Decimal | None = None
    calls: list[UUID] = field(default_factory=list)

    async def score(self, *, member_id: UUID, provider_id: UUID) -> Decimal | None:
        del provider_id
        self.calls.append(member_id)
        return self.value


@dataclass(frozen=True)
class TestDeviceKey:
    """Clé d'appareil de comptoir fictive (P-256)."""

    __test__ = False  # pas une classe de tests pytest

    private: int
    public_jwk: str

    @classmethod
    def generate(cls) -> TestDeviceKey:
        d = secrets.randbelow(ecdsa.N - 1) + 1
        x, y = ecdsa.public_point(d)
        jwk = {
            "crv": "P-256",
            "kty": "EC",
            "x": b64url(x.to_bytes(32)),
            "y": b64url(y.to_bytes(32)),
        }
        return cls(private=d, public_jwk=canonical_json(jwk).decode())

    def sign(self, message: bytes) -> str:
        e = int.from_bytes(hashlib.sha256(message).digest())
        while True:
            k = secrets.randbelow(ecdsa.N - 1) + 1
            r = ecdsa.public_point(k)[0] % ecdsa.N
            s = pow(k, -1, ecdsa.N) * (e + r * self.private) % ecdsa.N
            if r and s:
                return b64url(r.to_bytes(32) + s.to_bytes(32))


# --- Validation minimale des schémas JSON de specs/events.md ------------------------------------

_JSON_BLOCK = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def event_schemas() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for block in _JSON_BLOCK.findall(EVENTS_MD.read_text(encoding="utf-8")):
        doc = json.loads(block)
        if isinstance(doc.get("title"), str):
            out[doc["title"]] = doc
    return out


_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "null": (type(None),),
}


def _type_ok(value: object, expected: str) -> bool:
    if expected in {"integer", "number"} and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[expected])


def schema_errors(value: object, schema: dict[str, Any], path: str = "$") -> list[str]:  # noqa: PLR0912
    """Sous-ensemble de JSON Schema utilisé par events.md (type, const, enum, pattern…)."""
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: const {schema['const']!r} attendu, reçu {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} hors de {schema['enum']}")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, t) for t in types):
            return [*errors, f"{path}: type {types} attendu, reçu {type(value).__name__}"]
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: motif {schema['pattern']} non respecté")
        fmt = schema.get("format")
        if fmt == "uuid":
            UUID(value)
        elif fmt == "date-time":
            datetime.fromisoformat(value)
    if isinstance(value, int) and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: {value} < {schema['minimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: trop peu d'éléments")
        for i, item in enumerate(value):
            errors.extend(schema_errors(item, schema.get("items", {}), f"{path}[{i}]"))
    if isinstance(value, dict):
        props: dict[str, Any] = schema.get("properties", {})
        errors.extend(
            f"{path}: champ requis absent « {key} »"
            for key in schema.get("required", [])
            if key not in value
        )
        if schema.get("additionalProperties") is False:
            errors.extend(f"{path}: champ en trop « {key} »" for key in value if key not in props)
        for key, item in value.items():
            if key in props:
                errors.extend(schema_errors(item, props[key], f"{path}.{key}"))
        for clause in schema.get("allOf", []):
            if not schema_errors(value, clause.get("if", {}), path):
                errors.extend(schema_errors(value, clause.get("then", {}), path))
    return errors
