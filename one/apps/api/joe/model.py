"""Interface LLM interne de JOE : un protocole, un modèle déterministe, un adaptateur local.

Aucun SDK LLM (specs/DEPENDENCIES.md inchangé) :
- ``LanguageModel`` : protocole minimal (``name`` + ``complete``) ; le modèle est choisi par
  configuration (``MULEMA_JOE_MODEL``), jamais en dur dans le service ;
- ``DeterministicModel`` : défaut, hors réseau, reproductible. Il renvoie le brouillon calculé
  par les outils ; c'est aussi le repli quand le modèle configuré échoue (mode air-gapped) ;
- ``LocalModel`` : adaptateur local-first optionnel (API ``/api/generate`` au format Ollama),
  limité à la BOUCLE LOCALE et passé par le transport gardé de L9. Il n'est construit que si
  ``MULEMA_JOE_MODEL=local`` : sans configuration, aucune requête ne sort.

Le modèle ne reçoit qu'une ``ModelRequest`` pseudonymisée (``api.joe.pseudonym``) : jetons
``[ADH-1]``, ``[PEC-1]``…, jamais un nom, un numéro ou un identifiant interne. Il ne décide de
rien : la recommandation d'un brouillon est calculée avant lui, il n'en rédige que le texte.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, Protocol

from api.integrations.egress import EgressAllowlist, EgressDeniedError, Endpoint, is_loopback
from api.integrations.transport import (
    GuardedHttpTransport,
    HttpRequest,
    HttpTransport,
    split_destination,
)

type ModelTask = Literal["reponse", "brouillon_decision", "brouillon_message"]
type ModelKind = Literal["deterministe", "local"]

HTTP_OK: Final = 200
MAX_REPLY_CHARS: Final = 4000

_INSTRUCTIONS: Final[Mapping[ModelTask, str]] = {
    "reponse": (
        "Tu es JOE, assistant d'une mutuelle santé. Réponds en français simple, en trois "
        "phrases au plus, UNIQUEMENT à partir des faits fournis. Garde les jetons entre "
        "crochets tels quels. Tu ne décides rien et tu ne donnes aucun avis médical."
    ),
    "brouillon_decision": (
        "Tu es JOE. Rédige en français une justification courte de la recommandation fournie, "
        "UNIQUEMENT à partir des faits. Garde les jetons entre crochets. La décision appartient "
        "au médecin-conseil ; tu ne mentionnes aucune information médicale."
    ),
    "brouillon_message": (
        "Tu es JOE. Reformule ce SMS pour un adhérent en français simple, 300 caractères au "
        "plus, sans information médicale. Garde les jetons entre crochets."
    ),
}


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """Tout ce que le modèle reçoit : déjà pseudonymisé et vérifié."""

    task: ModelTask
    question: str
    facts: tuple[str, ...]
    draft: str

    def prompt(self) -> str:
        facts = "\n".join(f"- {fact}" for fact in self.facts) or "- (aucun)"
        return (
            f"{_INSTRUCTIONS[self.task]}\n\nQuestion : {self.question}\n\nFaits :\n{facts}\n\n"
            f"Brouillon :\n{self.draft}"
        )


class LanguageModel(Protocol):
    """Modèle de langage interchangeable (configurable, jamais importé d'un SDK)."""

    @property
    def name(self) -> str: ...

    async def complete(self, request: ModelRequest) -> str: ...


class ModelUnavailableError(RuntimeError):
    """Le modèle configuré n'a pas répondu (le service se replie sur le déterministe)."""


class DeterministicModel:
    """Modèle par défaut : hors réseau, même entrée = même sortie."""

    @property
    def name(self) -> str:
        return "joe-deterministe-v1"

    async def complete(self, request: ModelRequest) -> str:
        return request.draft


class LocalModel:
    """Adaptateur local-first (format Ollama), sur la boucle locale uniquement."""

    def __init__(self, *, base_url: str, model: str, transport: HttpTransport) -> None:
        try:
            _, host, _, _ = split_destination(base_url)
        except EgressDeniedError as exc:
            msg = "MULEMA_JOE_LOCAL_URL : URL HTTP de boucle locale attendue"
            raise ValueError(msg) from exc
        if not is_loopback(host):
            msg = f"modèle local : seule la boucle locale est admise, pas {host!r}"
            raise ValueError(msg)
        if not model:
            msg = "modèle local : nom de modèle vide"
            raise ValueError(msg)
        self._url = base_url.rstrip("/") + "/api/generate"
        self._model = model
        self._transport = transport

    @property
    def name(self) -> str:
        return f"local:{self._model}"

    async def complete(self, request: ModelRequest) -> str:
        body = json.dumps(
            {
                "model": self._model,
                "prompt": request.prompt(),
                "stream": False,
                "options": {"temperature": 0},
            },
            ensure_ascii=False,
        ).encode()
        try:
            response = await self._transport.send(
                HttpRequest(
                    method="POST",
                    url=self._url,
                    headers={"Content-Type": "application/json"},
                    body=body,
                )
            )
        except OSError as exc:  # EgressDeniedError, refus de connexion, délai dépassé
            raise ModelUnavailableError(type(exc).__name__) from exc
        if response.status != HTTP_OK:
            raise ModelUnavailableError(f"statut {response.status}")
        try:
            reply = json.loads(response.body)["response"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ModelUnavailableError("réponse illisible") from exc
        if not isinstance(reply, str) or not reply.strip():
            raise ModelUnavailableError("réponse vide")
        return reply.strip()[:MAX_REPLY_CHARS]


@dataclass(frozen=True, slots=True)
class JoeModelSettings:
    """``MULEMA_JOE_MODEL`` = ``deterministe`` (défaut) ou ``local`` (avec URL et modèle)."""

    kind: ModelKind = "deterministe"
    local_url: str | None = None
    local_model: str | None = None
    timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> JoeModelSettings:
        kind = environ.get("MULEMA_JOE_MODEL", "deterministe") or "deterministe"
        if kind == "deterministe":
            return cls()
        if kind != "local":
            msg = "MULEMA_JOE_MODEL : « deterministe » ou « local » attendu"
            raise ValueError(msg)
        url = environ.get("MULEMA_JOE_LOCAL_URL")
        model = environ.get("MULEMA_JOE_LOCAL_MODEL")
        if not url or not model:
            msg = "MULEMA_JOE_LOCAL_URL et MULEMA_JOE_LOCAL_MODEL requis avec le modèle local"
            raise ValueError(msg)
        return cls(kind="local", local_url=url, local_model=model)


def build_language_model(settings: JoeModelSettings) -> LanguageModel:
    """Modèle configuré. Le local n'est joignable que s'il figure AUSSI dans la liste blanche
    de l'instance (``infra/egress-allowlist.txt``) : la garde de l'application s'applique."""
    if settings.kind == "deterministe":
        return DeterministicModel()
    if settings.local_url is None or settings.local_model is None:
        msg = "MULEMA_JOE_LOCAL_URL et MULEMA_JOE_LOCAL_MODEL requis avec le modèle local"
        raise ValueError(msg)
    _, host, port, _ = split_destination(settings.local_url)
    transport = GuardedHttpTransport(
        EgressAllowlist(frozenset({Endpoint(host, port)})),
        timeout_seconds=settings.timeout_seconds,
    )
    return LocalModel(base_url=settings.local_url, model=settings.local_model, transport=transport)
