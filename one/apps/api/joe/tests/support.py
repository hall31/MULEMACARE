"""Aides des tests L8 : application de test, scénario fictif, modèle espion, serveur LLM local
simulé, instantané de la base.

Toutes les données sont fictives. Les noms et numéros ci-dessous existent pour vérifier qu'ils
ne sortent JAMAIS vers le modèle.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Self
from uuid import UUID

from fastapi.testclient import TestClient

from api.claims.ports import ClaimsRuntime
from api.claims.routes import install as install_claims
from api.claims.tests.conftest import APP_ROLE, ClaimsSeed, MemberRef
from api.claims.tests.flows import ITEMS_48000, ITEMS_185000, create_claim, identify
from api.core.app import create_app
from api.core.settings import Settings
from api.integrations.egress import EgressAllowlist, Endpoint
from api.integrations.healthos import HealthOSClient
from api.integrations.transport import GuardedHttpTransport
from api.joe.model import DeterministicModel, LanguageModel, ModelRequest
from api.joe.ports import member_reader_factory
from api.joe.routes import JoeRuntime
from api.joe.routes import install as install_joe
from api.members.cards import CardKeys

# Identité fictive volontairement reconnaissable (jamais vers le modèle).
GIVEN_NAME = "Aminata"
FAMILY_NAME = "Kouassi-Fictive"
BIRTH_DATE = "1987-03-14"


class SpyModel:
    """Modèle déterministe de test qui garde chaque requête reçue."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []
        self._inner = DeterministicModel()

    @property
    def name(self) -> str:
        return "espion-deterministe"

    async def complete(self, request: ModelRequest) -> str:
        self.requests.append(request)
        return await self._inner.complete(request)


@dataclass(frozen=True)
class Scenario:
    member: MemberRef
    auto_claim_id: str
    review_claim_id: str
    review_claim_number: str
    contribution_id: UUID

    def identifying_values(self) -> list[str]:
        """Tout ce qui ne doit jamais atteindre le modèle."""
        phone = self.member.phone or ""
        return [
            GIVEN_NAME,
            FAMILY_NAME,
            BIRTH_DATE,
            phone,
            phone.lstrip("+"),
            self.member.member_number,
            str(self.member.member_id),
            str(self.member.person_id),
            str(self.member.pseudonym),
            self.auto_claim_id,
            self.review_claim_id,
        ]


@dataclass
class JoeHarness:
    client: TestClient
    seed: ClaimsSeed
    spy: SpyModel
    scenario: Scenario


@contextmanager
def build_client(
    seed: ClaimsSeed, model: LanguageModel, *, extra_endpoints: Sequence[Endpoint] = ()
) -> Iterator[TestClient]:
    """API de test : noyau + L5 (pour fabriquer de vrais dossiers) + JOE."""
    allowlist = EgressAllowlist(
        frozenset({Endpoint("127.0.0.1", seed.healthos.port), *extra_endpoints})
    )
    app = create_app(
        Settings(database_url=seed.url, app_role=APP_ROLE, egress_allowlist=allowlist),
        identity_provider=seed.idp,
    )
    install_claims(
        app,
        ClaimsRuntime(
            healthos=HealthOSClient(
                base_url=seed.healthos.fhir_base_url,
                transport=GuardedHttpTransport(allowlist, timeout_seconds=2),
            ),
            qr_verifier=seed.qr,
            sms_sender=seed.sms,
            fraud_scorer=seed.fraud,
            clock=seed.clock,
        ),
    )
    install_joe(
        app,
        JoeRuntime(
            clock=seed.clock,
            model=model,
            members=member_reader_factory(seed.clock, CardKeys(secrets.token_bytes(32))),
        ),
    )
    with TestClient(app) as client:
        yield client


def build_scenario(client: TestClient, seed: ClaimsSeed) -> Scenario:
    """Un adhérent fictif, une cotisation en retard (30 j, droits encore ouverts), un dossier
    accordé automatiquement (48 000 FCFA) et un dossier en revue (185 000 FCFA)."""
    member = seed.new_member(unpaid_since=date(2026, 9, 1))
    with seed.owner() as conn:
        conn.execute(
            "UPDATE persons SET given_name = %s, family_name = %s, birth_date = %s WHERE id = %s",
            (GIVEN_NAME, FAMILY_NAME, date.fromisoformat(BIRTH_DATE), member.person_id),
        )
    auto = create_claim(client, seed, identify(client, seed, member), ITEMS_48000)
    assert auto.status_code == 201, auto.text
    assert auto.json()["claim"]["status"] == "accordee_auto"
    review = create_claim(client, seed, identify(client, seed, member), ITEMS_185000)
    assert review.status_code == 201, review.text
    assert review.json()["claim"]["status"] == "en_revue"
    contribution = seed.scalar(
        "SELECT id FROM contributions WHERE member_id = %s", (member.member_id,)
    )
    return Scenario(
        member=member,
        auto_claim_id=str(auto.json()["claim"]["id"]),
        review_claim_id=str(review.json()["claim"]["id"]),
        review_claim_number=str(review.json()["claim"]["claim_number"]),
        contribution_id=contribution,
    )


def snapshot(seed: ClaimsSeed, *, exclude: frozenset[str] = frozenset()) -> dict[str, str]:
    """Empreinte de chaque table (lecture propriétaire, hors RLS) : tout changement la modifie."""
    with seed.owner() as conn:
        tables = [
            str(r[0])
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
            ).fetchall()
        ]
        out: dict[str, str] = {}
        for table in tables:
            if table in exclude:
                continue
            row = conn.execute(
                f"SELECT count(*)::text || ':' || coalesce(md5(string_agg(t::text, '|' "
                f"ORDER BY t::text)), '') FROM {table} t".encode()
            ).fetchone()
            assert row is not None
            out[table] = str(row[0])
    return out


def ai_actions(seed: ClaimsSeed, user_id: UUID) -> list[dict[str, Any]]:
    with seed.owner() as conn:
        rows = conn.execute(
            "SELECT id, kind, tool, model, sources, input, output FROM ai_actions "
            "WHERE user_id = %s ORDER BY occurred_at, id",
            (user_id,),
        ).fetchall()
    return [
        {
            "id": str(r[0]),
            "kind": r[1],
            "tool": r[2],
            "model": r[3],
            "sources": r[4],
            "input": r[5],
            "output": r[6],
        }
        for r in rows
    ]


_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def leaks(text: str, values: Sequence[str]) -> list[str]:
    """Valeurs identifiantes présentes dans ``text`` (insensible à la casse), et tout UUID."""
    lowered = text.lower()
    found = [v for v in values if v and v.lower() in lowered]
    found.extend(_UUID.findall(text))
    return found


# --- Serveur LLM local simulé (boucle locale, port éphémère) ---------------------------------


@dataclass
class _LlmState:
    bodies: list[bytes] = field(default_factory=list)
    reply: str = "Réponse du modèle local pour [ADH-1]."
    fail_with: int | None = None


class _LlmHandler(BaseHTTPRequestHandler):
    server: _LlmServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: ANN401
        del format, args

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        state = self.server.state
        state.bodies.append(body)
        if state.fail_with is not None:
            self.send_response(state.fail_with)
            self.end_headers()
            return
        payload = json.dumps({"response": state.reply}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class _LlmServer(ThreadingHTTPServer):
    def __init__(self, state: _LlmState) -> None:
        self.state = state
        super().__init__(("127.0.0.1", 0), _LlmHandler)


class FakeLocalLlm:
    """Faux serveur de modèle local (format Ollama ``/api/generate``)."""

    def __init__(self) -> None:
        self.state = _LlmState()
        self.port = 0
        self._server: _LlmServer | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Self:
        self._server = _LlmServer(self.state)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def bodies(self) -> list[bytes]:
        return list(self.state.bodies)
