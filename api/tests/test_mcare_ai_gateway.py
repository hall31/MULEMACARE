"""MCare AI passe par le tronc IA — et seulement par lui.

Un transport espion est injecté dans la Gateway du tronc
(``build_mcare_gateway(transport=...)``) ; il enregistre chaque appel et ne
sort jamais sur le réseau. Trois promesses :

- (a) avec une clé, l'appel traverse la Gateway : le modèle rapporté
  (``model``, ``llm_model``) est celui qu'elle a routé, jamais une constante ;
- (b) sans clé, les réponses gardent leur forme d'avant et rien ne part ;
- (c) les garde-fous s'exécutent avant l'appel LLM (activation, adhésion,
  quota), et l'évaluation clinique s'applique toujours à la sortie du tronc.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import pytest
from cybernecs_agent_core.gateway import TransportResult
from fastapi.testclient import TestClient

from app.domain.mcare_models import SpecialistType
from app.services import mcare_agents
from app.services.mcare_agents import MCareAgentError, SpecialistAgent, build_mcare_gateway

_PROVIDER_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "MISTRAL_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "VOYAGE_API_KEY",
)

SAFE_REPLY = (
    "Hypothèse à explorer : une infection virale est possible. "
    "Une consultation avec un médecin est recommandée."
)
DIAGNOSIS_REPLY = (
    "Vous avez une pneumonie. Vous souffrez de une infection pulmonaire. "
    "C'est certainement grave."
)


class SpyTransport:
    """Transport du tronc remplacé : enregistre chaque appel, ne sort jamais."""

    def __init__(self, content: str = SAFE_REPLY, fail_first: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._content = content
        self._fail_first = fail_first

    async def __call__(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        context: Any = None,
    ) -> TransportResult:
        self.calls.append({"model": model, "messages": messages, "max_tokens": max_tokens})
        if len(self.calls) <= self._fail_first:
            raise RuntimeError(f"provider down for {model}")
        return TransportResult(
            content=self._content, prompt_tokens=12, completion_tokens=7, cost_usd=0.0
        )


@pytest.fixture(autouse=True)
def isolated_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aucune clé fournisseur, aucune Gateway héritée d'un test précédent."""
    for name in (*_PROVIDER_KEYS, "CYBERNECS_AI_OFF"):
        monkeypatch.delenv(name, raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(mcare_agents, "_gateway", None)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "mcare_gateway.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("JWT_SECRET", "gateway-jwt-secret-key-32chars-min!")
    monkeypatch.setenv("MCARE_ENABLED", "true")
    monkeypatch.setenv("MULEMACARE_HEALTHOS_BRIDGE_ENABLED", "false")

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core import db as dbmod
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    dbmod.engine = create_async_engine(settings.database_url, echo=False)
    dbmod.SessionLocal = async_sessionmaker(dbmod.engine, expire_on_commit=False)

    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _headers(client: TestClient) -> dict[str, str]:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "mcare-gw@mulemacare.example", "password": "secret12345", "role": "OPS"},
    )
    if r.status_code == 409:
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "mcare-gw@mulemacare.example", "password": "secret12345"},
        )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _wire(monkeypatch: pytest.MonkeyPatch, spy: SpyTransport, *, with_key: bool = True) -> None:
    if with_key:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(mcare_agents, "_gateway", build_mcare_gateway(transport=spy))


def _chat(client: TestClient, headers: dict[str, str], cssa_id: str = "CSSA-MC0042"):
    return client.post(
        "/api/v1/mcare/chat",
        headers=headers,
        json={"cssa_id": cssa_id, "message": "J'ai de la fièvre depuis hier"},
    )


# ── (a) l'appel passe par la Gateway du tronc ───────────────────────────────


def test_specialist_agent_calls_the_trunk_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    spy = SpyTransport()
    agent = SpecialistAgent(SpecialistType.TRIAGE, gateway=build_mcare_gateway(transport=spy))

    result = asyncio.run(
        agent.chat(
            "J'ai de la fièvre",
            conversation_history=[
                {"role": "user", "content": "Bonjour"},
                {"role": "assistant", "content": "Bonjour, je vous écoute."},
            ],
        )
    )

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert [m["role"] for m in call["messages"]] == ["system", "user", "assistant", "user"]
    assert "MCare Triage" in call["messages"][0]["content"]
    assert call["messages"][-1]["content"] == "J'ai de la fièvre"
    assert call["max_tokens"] == 1024
    assert result["response"] == SAFE_REPLY
    assert result["model"] == call["model"]
    assert result["usage"] == {"input_tokens": 12, "output_tokens": 7}
    assert result["safety_check"]["passed"] is True
    assert result["clin_card"] is not None


def test_chat_route_goes_through_the_trunk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport()
    _wire(monkeypatch, spy)

    r = _chat(client, _headers(client))

    assert r.status_code == 200, r.text
    body = r.json()
    assert len(spy.calls) == 1
    assert body["message"] == SAFE_REPLY
    assert body["specialist_type"] == "triage"
    assert body["tags"] == ["IA", "Hypothèses non validées"]
    assert body["quota_remaining"] == 14
    assert body["safety_check"]["passed"] is True


def test_health_check_reports_the_model_routed_by_the_trunk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport()
    _wire(monkeypatch, spy)

    body = client.get("/api/v1/mcare/health-check").json()

    assert len(spy.calls) == 1
    assert body["status"] == "healthy"
    assert body["llm_available"] is True
    assert body["llm_model"] == spy.calls[0]["model"]
    assert isinstance(body["llm_latency_ms"], int)


def test_provider_failure_becomes_a_503_not_a_simulated_answer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport(fail_first=99)
    _wire(monkeypatch, spy)
    headers = _headers(client)

    r = _chat(client, headers)
    health = client.get("/api/v1/mcare/health-check").json()

    assert spy.calls, "la Gateway doit avoir essayé sa chaîne de fallback"
    assert r.status_code == 503
    assert r.json()["detail"].startswith("MCare AI error: LLM unavailable")
    assert health["status"] == "degraded"
    assert health["llm_available"] is False
    assert "provider down" in health["error"]


# ── (b) sans clé : chemin hors ligne inchangé ───────────────────────────────


def test_without_key_chat_keeps_its_503_and_sends_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport()
    _wire(monkeypatch, spy, with_key=False)

    r = _chat(client, _headers(client))

    assert r.status_code == 503
    assert r.json()["detail"] == "Claude API not configured (set ANTHROPIC_API_KEY)"
    assert spy.calls == []


def test_without_key_health_check_keeps_its_shape(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport()
    _wire(monkeypatch, spy, with_key=False)

    health = client.get("/api/v1/mcare/health-check").json()

    assert health == {
        "status": "unavailable",
        "llm_available": False,
        "llm_model": "none",
        "llm_latency_ms": None,
        "mcare_enabled": True,
        "error": "Claude API not configured",
    }
    assert spy.calls == []


def test_without_key_the_agent_refuses_to_start() -> None:
    with pytest.raises(MCareAgentError, match="ANTHROPIC_API_KEY not configured"):
        SpecialistAgent(SpecialistType.GENERAL)


# ── (c) garde-fous avant l'appel LLM, évaluation clinique après ─────────────


def test_disabled_mcare_blocks_before_the_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport()
    _wire(monkeypatch, spy)
    headers = _headers(client)
    monkeypatch.setenv("MCARE_ENABLED", "false")

    r = _chat(client, headers)

    assert r.status_code == 503
    assert spy.calls == []


def test_inactive_membership_blocks_before_the_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport()
    _wire(monkeypatch, spy)
    headers = _headers(client)
    created = client.post(
        "/api/v1/members",
        headers=headers,
        json={"cssa_id": "CSSA-MC0077", "status": "PENDING_PAYMENT"},
    )
    assert created.status_code == 200, created.text

    r = _chat(client, headers, cssa_id="CSSA-MC0077")

    assert r.status_code == 402
    assert spy.calls == []


def test_exhausted_quota_blocks_before_the_llm(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport()
    _wire(monkeypatch, spy)
    headers = _headers(client)
    created = client.post(
        "/api/v1/members",
        headers=headers,
        json={"cssa_id": "CSSA-MC0088", "status": "ACTIVE"},
    )
    assert created.status_code == 200, created.text

    for _ in range(15):
        assert _chat(client, headers, cssa_id="CSSA-MC0088").status_code == 200
    exhausted = _chat(client, headers, cssa_id="CSSA-MC0088")

    assert exhausted.status_code == 402
    assert exhausted.json()["detail"] == "MCare AI quota exhausted"
    assert len(spy.calls) == 15, "le 16e message ne doit jamais atteindre le LLM"


def test_clinical_safety_still_evaluates_the_trunk_output(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = SpyTransport(content=DIAGNOSIS_REPLY)
    _wire(monkeypatch, spy)

    r = _chat(client, _headers(client))

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["safety_check"]["passed"] is False
    assert body["safety_check"]["diagnosis_detected"] is True
    assert body["clin_card"] is None


# ── hygiène : aucun modèle nommé dans l'application ─────────────────────────


def test_mcare_code_names_no_model() -> None:
    api_root = Path(mcare_agents.__file__).resolve().parents[1]
    for rel in ("services/mcare_agents.py", "api/mcare_ai.py"):
        source = (api_root / rel).read_text(encoding="utf-8")
        assert not re.search(r"\b(?:gpt-[\w.]+|gemini-[\w.]+|claude-[\w.-]+)", source), rel
