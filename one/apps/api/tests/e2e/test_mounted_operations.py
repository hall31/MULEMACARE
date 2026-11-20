"""Contrat : chaque ``operationId`` de specs/openapi.yaml est monté dans l'application assemblée.

Une opération du contrat sans route est un échec, avec la liste des opérations manquantes.
Aucune exclusion : toutes les opérations du contrat sont montées.
Une route montée hors contrat est aussi un échec. Pas de démarrage (aucune base) : seule la
table de routage de ``create_app(..., modules=...)`` est lue, via son schéma OpenAPI généré.

Lien route → opération : chaque route montée (méthode + chemin) dépend de
``require_operation(<operationId>)`` avec l'``operationId`` que le contrat déclare pour CETTE
méthode et CE chemin. Une route montée sans garde, avec la garde d'une autre opération, ou sous un
autre ``operationId`` est un échec. Seules les opérations sans jeton du contrat (``security``
autre que ``bearerAuth``) n'ont pas de garde, et elles sont exactement
``UNAUTHENTICATED_OPERATIONS``.
"""

from __future__ import annotations

import inspect
import re
import secrets
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from api.claims.ports import ClaimsRuntime, SimulatedSmsSender
from api.core.app import AppModules, create_app
from api.core.context import require_operation
from api.core.identity import InMemoryIdentityProvider
from api.core.permissions import UNAUTHENTICATED_OPERATIONS
from api.core.ratelimit import RateLimits
from api.core.settings import Settings, deny_all_egress
from api.integrations.healthos import HealthOSClient
from api.integrations.transport import GuardedHttpTransport
from api.joe.model import JoeModelSettings, build_language_model
from api.joe.ports import member_reader_factory
from api.joe.service import JoeRuntime
from api.members.cards import CardKeys, CardQrVerifier
from api.members.routes import MembersRuntime
from api.metrics.runtime import MetricsRuntime
from api.payments.channels import ChannelRegistry
from api.payments.config import PaymentsConfig
from api.payments.routes import PaymentsRuntime
from api.rules.routes import RulesRuntime
from api.tests.e2e.conftest import PUBLIC_BASE_URL, START, TestClock
from api.tests.paths import OPENAPI_YAML

_OPERATION_ID = re.compile(r"^\s+operationId:\s*([A-Za-z0-9_]+)\s*$", re.MULTILINE)


def _contract_operations() -> frozenset[str]:
    return frozenset(_OPERATION_ID.findall(OPENAPI_YAML.read_text(encoding="utf-8")))


def assembled_app(rate_limits: RateLimits | None = None) -> FastAPI:
    """Application assemblée sans base (table de routage, middlewares) ; réutilisée par L10."""
    clock = TestClock(START)
    card_keys = CardKeys(secrets.token_bytes(32))
    modules = AppModules(
        members=MembersRuntime(clock=clock, card_keys=card_keys),
        payments=PaymentsRuntime(
            clock=clock,
            config=PaymentsConfig(
                link_secret=secrets.token_bytes(32),
                public_base_url=PUBLIC_BASE_URL,
                channels=ChannelRegistry([]),
            ),
        ),
        claims=ClaimsRuntime(
            healthos=HealthOSClient(
                base_url="https://healthos.invalid/fhir",
                transport=GuardedHttpTransport(deny_all_egress(), timeout_seconds=1),
            ),
            qr_verifier=CardQrVerifier(card_keys),
            sms_sender=SimulatedSmsSender(),
            clock=clock,
        ),
        rules=RulesRuntime(clock=clock),
        joe=JoeRuntime(
            clock=clock,
            model=build_language_model(JoeModelSettings.from_env({})),
            members=member_reader_factory(clock, card_keys),
        ),
        metrics=MetricsRuntime(clock=clock, pseudonym_key=secrets.token_bytes(32)),
    )
    return create_app(
        # Documentation exposée (mode développement) : ses routes sont contrôlées ci-dessous.
        Settings(
            database_url="postgresql+psycopg:///inutilise",
            environment="development",
            expose_docs=True,
        ),
        identity_provider=InMemoryIdentityProvider(),
        modules=modules,
        rate_limits=rate_limits,
    )


def _mounted_operations() -> frozenset[str]:
    app = assembled_app()
    # Schéma généré par l'application : reflète les routes réellement servies (y compris les
    # routeurs inclus, que FastAPI imbrique dans ``app.routes``).
    paths: dict[str, dict[str, Any]] = app.openapi()["paths"]
    return frozenset(
        str(operation["operationId"])
        for methods in paths.values()
        for operation in methods.values()
        if isinstance(operation, dict) and "operationId" in operation
    )


def test_chaque_operation_du_contrat_est_montee() -> None:
    missing = sorted(_contract_operations() - _mounted_operations())
    assert missing == [], f"opérations du contrat sans route : {missing}"


def test_aucune_route_hors_contrat() -> None:
    extra = sorted(_mounted_operations() - _contract_operations())
    assert extra == [], f"routes montées hors contrat : {extra}"


# --- Lien route → opération : chaque route montée porte la garde de SON operationId -------------

_PATH_LINE = re.compile(r"^  (/\S*):\s*$")
_METHOD_LINE = re.compile(r"^    (get|post|put|patch|delete):\s*$")
_OPERATION_LINE = re.compile(r"^      operationId: (\w+)\s*$")
_SECURITY_LINE = re.compile(r"^      security:")
_BEARER_ONLY = re.compile(r"^      security:\s*\n\s+- bearerAuth: \[\]", re.MULTILINE)
# Routes de documentation ajoutées par FastAPI elle-même (pas des opérations du contrat).
FASTAPI_DOC_ROUTES = frozenset({"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})
# Sondes d'exploitation (L10, hors contrat d'API, CR-L10-01) : seules routes non-API admises.
PROBE_ROUTES = frozenset({"/healthz", "/readyz"})


def _contract_routes() -> dict[tuple[str, str], tuple[str, bool]]:
    """(MÉTHODE, chemin) → (operationId, avec jeton ?), lus dans la section ``paths`` du contrat.

    Une opération est « avec jeton » si elle hérite de la sécurité globale (``bearerAuth``) ;
    ``security: []`` ou une autre sécurité (signature de webhook) la rend « sans jeton ».
    """
    spec = OPENAPI_YAML.read_text(encoding="utf-8")
    paths = spec.split("\npaths:\n", 1)[1].split("\ncomponents:\n", 1)[0]
    routes: dict[tuple[str, str], tuple[str, bool]] = {}
    path = method = operation = None
    block: list[str] = []

    def flush() -> None:
        if path and method:
            assert operation, f"{method} {path} sans operationId"
            own = "\n".join(block)
            overridden = any(_SECURITY_LINE.match(line) for line in block)
            routes[(method, path)] = (operation, not overridden or bool(_BEARER_ONLY.search(own)))

    for line in paths.splitlines():
        if found := _PATH_LINE.match(line):
            flush()
            path, method, operation, block = found.group(1), None, None, []
        elif found := _METHOD_LINE.match(line):
            flush()
            method, operation, block = found.group(1).upper(), None, []
        elif method:
            block.append(line)
            if found := _OPERATION_LINE.match(line):
                operation = found.group(1)
    flush()
    return routes


_GUARD_CODE = require_operation("getCurrentUser").__code__


def _calls(dependant: Dependant) -> list[Callable[..., Any]]:
    found = [dependant.call] if dependant.call is not None else []
    for sub in dependant.dependencies:
        found += _calls(sub)
    return found


def _guards(dependant: Dependant) -> list[str]:
    """Opérations de toutes les gardes ``require_operation`` de l'arbre de dépendances."""
    return [
        str(inspect.getclosurevars(call).nonlocals["operation"])
        for call in _calls(dependant)
        if getattr(call, "__code__", None) is _GUARD_CODE
    ]


def _mounted_routes() -> dict[tuple[str, str], tuple[str | None, list[str]]]:
    """(MÉTHODE, chemin) → (operationId de la route, gardes), routeurs inclus aplatis."""
    mounted: dict[tuple[str, str], tuple[str | None, list[str]]] = {}
    other: set[str] = set()
    for route in iter_route_contexts(assembled_app().routes):
        if not isinstance(route.original_route, APIRoute):
            other.add(str(route.path))
            continue
        for method in route.methods or ():
            key = (method, str(route.path))
            assert key not in mounted, f"route montée deux fois : {key}"
            mounted[key] = (route.operation_id, _guards(route.dependant))
    # Toute autre route (Starlette brute, montage) échapperait à ce contrôle : interdite.
    assert other == FASTAPI_DOC_ROUTES | PROBE_ROUTES, (
        f"routes non-API inattendues : {sorted(other)}"
    )
    return mounted


def test_le_contrat_est_lu() -> None:
    """Garde-fou du lecteur : chaque operationId du contrat est rattaché à une route."""
    routes = _contract_routes()
    assert sorted(op for op, _ in routes.values()) == sorted(_contract_operations())
    public = {op for op, bearer in routes.values() if not bearer}
    assert public == UNAUTHENTICATED_OPERATIONS


def test_chaque_route_montee_porte_la_garde_de_son_operation() -> None:
    contract = _contract_routes()
    mounted = _mounted_routes()
    assert set(mounted) == set(contract), (
        f"routes hors contrat {sorted(set(mounted) - set(contract))}, "
        f"routes du contrat non montées {sorted(set(contract) - set(mounted))}"
    )
    wrong: list[str] = []
    for key, (operation_id, guards) in sorted(mounted.items()):
        expected, bearer = contract[key]
        expected_guards = [expected] if bearer else []
        if operation_id != expected or guards != expected_guards:
            wrong.append(
                f"{key[0]} {key[1]} : operationId {operation_id!r} (contrat {expected!r}), "
                f"gardes {guards} (attendu {expected_guards})"
            )
    assert wrong == [], "\n".join(wrong)
