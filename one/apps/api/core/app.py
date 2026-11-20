"""Fabrique de l'application : base, identité, identifiant de requête, erreurs problem+json.

Application assemblée : ``create_app(settings, identity_provider=..., modules=AppModules(...))``
monte noyau (L1) + produits et règles (L2) + grand livre (L3) + adhérents et cotisations (L4) +
comptoir et prises en charge (L5) + JOE (L8) + espace adhérent et diaspora (P1) + mesure
produit (P2) + marque blanche, espaces assureur et employeur, plateforme (P3) avec leurs
dépendances. Sans ``modules``, seuls le noyau et le
grand livre sont montés (tests d'un lot isolé, qui installent ensuite leur propre module). Le
grand livre (L3) est toujours installé ici. La garde d'egress (R9) entoure toute la vie de
l'application. Le fournisseur d'identité est obligatoire (aucun défaut, pour qu'une
implémentation de test ne parte jamais en production par oubli).

Exploitation (L10) : sondes ``/healthz`` et ``/readyz`` (``api.core.health``, hors contrat),
limitation de débit par IP et par jeton (``api.core.ratelimit``, active par défaut) ;
``/docs``, ``/redoc`` et ``/openapi.json`` ne sont servis que si ``settings.expose_docs``
(jamais en production). Point d'entrée de production : ``api.main``.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Final
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.branding.domains import ReservedDomains
from api.branding.routes import install as install_branding
from api.branding.service import BrandingPorts, BrandingRuntime
from api.claims.ports import ClaimsRuntime
from api.claims.routes import install as install_claims
from api.core.context import request_id_of
from api.core.database import Database
from api.core.errors import (
    DomainError,
    FieldError,
    InternalError,
    NotAuthenticatedError,
    NotFoundError,
    RoleForbiddenError,
    ValidationFailedError,
)
from api.core.health import install_probes
from api.core.identity import IdentityProvider
from api.core.jsonlog import LOGGER_NAME, log_event, log_exception
from api.core.ratelimit import RateLimitMiddleware, RateLimits, missing_operations
from api.core.routes import router as core_router
from api.core.settings import Settings
from api.integrations.egress import egress_guard
from api.joe.routes import install as install_joe
from api.joe.service import JoeRuntime
from api.ledger.routes import install as install_ledger
from api.member_space.routes import install as install_member_space
from api.members.routes import MembersRuntime
from api.members.routes import install as install_members
from api.metrics.routes import install as install_metrics
from api.metrics.runtime import MetricsRuntime
from api.partners.routes import install as install_partners
from api.partners.service import PartnersRuntime
from api.payments.routes import PaymentsRuntime
from api.payments.routes import install as install_payments
from api.rules.routes import RulesRuntime
from api.rules.routes import install as install_rules

logger = logging.getLogger(f"{LOGGER_NAME}.http")

REQUEST_ID_HEADER: Final = "X-Request-ID"
_REQUEST_ID: Final = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
PROBLEM_JSON: Final = "application/problem+json"


def problem_response(error: DomainError, request_id: str) -> JSONResponse:
    body: dict[str, Any] = {
        "code": error.code.value,
        "message": error.message,
        "action": error.action,
        "request_id": request_id,
    }
    if error.errors:
        body["errors"] = [{"field": e.field, "message": e.message} for e in error.errors]
    retry_after = getattr(error, "retry_after_seconds", None)
    if isinstance(retry_after, int):
        body["retry_after_seconds"] = retry_after
    return JSONResponse(
        body,
        status_code=error.status_code,
        media_type=PROBLEM_JSON,
        headers={REQUEST_ID_HEADER: request_id},
    )


def _field_path(location: Sequence[int | str]) -> str:
    parts = [str(p) for p in location]
    if parts and parts[0] in {"body", "query", "path", "header"}:
        parts = parts[1:]
    return ".".join(parts) or "requete"


_HTTP_ERRORS: Final[dict[int, type[DomainError]]] = {
    status.HTTP_401_UNAUTHORIZED: NotAuthenticatedError,
    status.HTTP_403_FORBIDDEN: RoleForbiddenError,
    status.HTTP_404_NOT_FOUND: NotFoundError,
}


async def _on_domain_error(request: Request, exc: Exception) -> Response:
    error = exc if isinstance(exc, DomainError) else InternalError()
    return problem_response(error, request_id_of(request))


async def _on_validation_error(request: Request, exc: Exception) -> Response:
    details = exc.errors() if isinstance(exc, RequestValidationError) else []
    errors = tuple(
        FieldError(_field_path(e.get("loc", ())), "Valeur manquante ou invalide.") for e in details
    )
    return problem_response(ValidationFailedError(errors=errors), request_id_of(request))


async def _on_http_error(request: Request, exc: Exception) -> Response:
    """Erreurs du routeur (route inconnue, méthode non permise) rendues en problem+json."""
    code = (
        exc.status_code
        if isinstance(exc, StarletteHTTPException)
        else status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    if code in _HTTP_ERRORS:
        mapped: DomainError = _HTTP_ERRORS[code]()
    elif code < status.HTTP_500_INTERNAL_SERVER_ERROR:
        mapped = ValidationFailedError()
    else:
        mapped = InternalError()
    response = problem_response(mapped, request_id_of(request))
    if code == status.HTTP_405_METHOD_NOT_ALLOWED:
        response.status_code = code
    return response


async def _on_unexpected_error(request: Request, exc: Exception) -> Response:
    # Type et pile seulement : le message peut contenir une valeur saisie (jsonlog).
    logger.error(
        "http.unexpected_error",
        exc_info=exc,
        extra={"fields": {"request_id": request_id_of(request)}},
    )
    return problem_response(InternalError(), request_id_of(request))


async def _request_id_and_access_log(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    request_id = incoming if _REQUEST_ID.fullmatch(incoming) else f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    route = request.scope.get("route")
    org = getattr(request.state, "organization_id", None)
    user = getattr(request.state, "user_id", None)
    log_event(
        logger,
        logging.INFO,
        "http.request",
        request_id=request_id,
        method=request.method,
        route=getattr(route, "path", "inconnue"),
        status=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
        organization_id=str(org) if org else None,
        user_id=str(user) if user else None,
    )
    return response


@dataclass(frozen=True, slots=True)
class AppModules:
    """Dépendances des modules métier de l'application assemblée (toutes obligatoires, sauf
    ``branding`` : ports de la marque blanche, sûrs par défaut — aucun hôte de logo externe,
    aucune preuve DNS, donc aucun domaine personnalisé servi)."""

    members: MembersRuntime
    payments: PaymentsRuntime
    claims: ClaimsRuntime
    rules: RulesRuntime
    joe: JoeRuntime
    metrics: MetricsRuntime
    branding: BrandingPorts = field(default_factory=BrandingPorts)


def _branding_runtime(settings: Settings, modules: AppModules) -> BrandingRuntime:
    """Domaines réservés : hôte du lien de paiement public, toutes les destinations de la liste
    blanche (HealthOS, bases) et leurs zones parentes, en plus des zones intégrées (CR-P3-02).
    Hôtes de logo : liste DÉDIÉE (``BrandingPorts.logo_hosts``), jamais la liste d'egress."""
    ports = modules.branding
    hosts = [
        urlsplit(modules.payments.config.public_base_url).hostname or "",
        *(endpoint.host for endpoint in settings.egress_allowlist.endpoints),
        *ports.reserved_hosts,
    ]
    return BrandingRuntime(
        logo_hosts=ports.logo_hosts,
        reserved=ReservedDomains.for_instance(hosts),
        dns=ports.dns,
        clock=modules.metrics.clock,
    )


def create_app(
    settings: Settings,
    *,
    identity_provider: IdentityProvider,
    routers: Sequence[APIRouter] = (),
    modules: AppModules | None = None,
    rate_limits: RateLimits | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # R9 : garde d'egress active pendant toute la vie de l'application, avant tout I/O.
        with egress_guard(settings.egress_allowlist):
            database = Database(settings.database_url, app_role=settings.app_role)
            try:
                try:
                    await database.verify_isolation_enforced(
                        strict_login=settings.strict_database_login
                    )
                except Exception:
                    log_exception(logger, "startup.refused")  # type et pile, sans valeur
                    raise
                app.state.database = database
                log_event(logger, logging.INFO, "app.started", environment=settings.environment)
                yield
            finally:
                await database.dispose()
                log_event(logger, logging.INFO, "app.stopped")

    docs = settings.expose_docs
    app = FastAPI(
        title="MulemaCare One API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.identity_provider = identity_provider
    # Sous pytest, la même IP TestClient épuise vite les seaux (60/min) : les tests L10
    # passent un RateLimits explicite ; le reste de la suite tourne sans plafond.
    if rate_limits is not None:
        limits = rate_limits
    elif "pytest" in sys.modules or os.environ.get("MULEMA_DISABLE_RATE_LIMIT") == "1":
        limits = RateLimits(rules={})
    else:
        limits = RateLimits()
    # Ajouté AVANT le middleware d'identifiant de requête, donc plus intérieur : un 429 porte
    # l'identifiant de requête et passe par le journal d'accès.
    app.add_middleware(RateLimitMiddleware, routes=lambda: app.routes, limits=limits)
    app.middleware("http")(_request_id_and_access_log)
    app.add_exception_handler(DomainError, _on_domain_error)
    app.add_exception_handler(RequestValidationError, _on_validation_error)
    app.add_exception_handler(StarletteHTTPException, _on_http_error)
    app.add_exception_handler(Exception, _on_unexpected_error)
    app.include_router(core_router)
    install_ledger(app)  # L3 : grand livre, autorisé par require_operation du noyau
    if modules is not None:
        install_rules(app, modules.rules)  # L2 produits, réseau, barème, règles
        install_members(app, modules.members)  # L4 adhérents
        install_payments(app, modules.payments)  # L4 cotisations, webhooks signés
        install_claims(app, modules.claims)  # L5 comptoir et prises en charge
        install_joe(app, modules.joe)  # L8 JOE : lecture et préparation, jamais de décision
        install_member_space(app)  # P1 espace adhérent : réutilise les runtimes L4 ci-dessus
        install_metrics(app, modules.metrics)  # P2 mesure produit : sans traceur tiers
        # P3 marque blanche, espaces assureur et employeur, plateforme (même horloge que P2 ;
        # hôtes de logo : liste dédiée, domaines réservés et preuve DNS — CR-P3-02).
        install_branding(app, _branding_runtime(settings, modules))
        install_partners(app, PartnersRuntime(clock=modules.metrics.clock))
    for router in routers:
        app.include_router(router)
    install_probes(app)
    if modules is not None and (missing := missing_operations(app.routes, limits.rules)):
        msg = f"limitation de débit : opérations introuvables {missing}"
        raise RuntimeError(msg)
    return app
