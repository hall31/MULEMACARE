"""Routes L2 (specs/openapi.yaml, tags ``produits`` et ``regles``) : route → service → dépôt.

Câblage noyau (L1) : ``require_operation("<operationId>")`` (``OPERATION_ROLES``, recopie des
``x-roles`` du contrat) ; l'organisation vient TOUJOURS du jeton, jamais d'un paramètre ni d'un
corps. Montage : ``install(app, RulesRuntime(clock=...))`` par ``api.core.app.create_app``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Final
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Path, Query, Request, status
from fastapi.responses import JSONResponse

from api.core.clock import Clock
from api.core.context import RequestContext, request_id_of, require_operation
from api.core.jsonlog import LOGGER_NAME, log_event
from api.rules.errors import RulesError
from api.rules.schemas import (
    RULE_CODE_PATTERN,
    Act,
    ActList,
    CreateActRequest,
    CreatePlanRequest,
    CreatePlanVersionRequest,
    CreateProviderConventionRequest,
    CreateProviderRequest,
    CreateRuleVersionRequest,
    CreateTariffItemRequest,
    Decision,
    EvaluateRulesRequest,
    Plan,
    PlanList,
    PlanVersion,
    Provider,
    ProviderConvention,
    ProviderList,
    RuleList,
    RuleVersion,
    RuleVersionList,
    TariffItem,
    TariffList,
)
from api.rules.service import CatalogService

logger = logging.getLogger(f"{LOGGER_NAME}.rules.routes")

STATE_KEY: Final = "l2_rules"
PROBLEM_JSON: Final = "application/problem+json"
REQUEST_ID_HEADER: Final = "X-Request-ID"


@dataclass(frozen=True, slots=True)
class RulesRuntime:
    """Dépendances du module : horloge UTC (jour courant, échéance de revue simulée)."""

    clock: Clock


def get_runtime(request: Request) -> RulesRuntime:
    runtime = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(runtime, RulesRuntime):  # pragma: no cover — installé par create_app
        msg = "module L2 non installé"
        raise TypeError(msg)
    return runtime


Runtime = Annotated[RulesRuntime, Depends(get_runtime)]
AtDate = Annotated[date | None, Query(alias="at", description="Date d'évaluation.")]
RuleCode = Annotated[str, Path(pattern=RULE_CODE_PATTERN, description="Code de la règle.")]

router = APIRouter(prefix="/v1")


def _service(ctx: RequestContext, runtime: RulesRuntime) -> CatalogService:
    return CatalogService(ctx=ctx, clock=runtime.clock)


# --- Produits ----------------------------------------------------------------------------------


@router.get("/plans", tags=["produits"], operation_id="listPlans", status_code=status.HTTP_200_OK)
async def list_plans(
    ctx: Annotated[RequestContext, Depends(require_operation("listPlans"))], runtime: Runtime
) -> PlanList:
    return await _service(ctx, runtime).list_plans()


@router.post(
    "/plans", tags=["produits"], operation_id="createPlan", status_code=status.HTTP_201_CREATED
)
async def create_plan(
    body: CreatePlanRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createPlan"))],
    runtime: Runtime,
) -> Plan:
    return await _service(ctx, runtime).create_plan(body)


@router.get(
    "/plans/{plan_id}", tags=["produits"], operation_id="getPlan", status_code=status.HTTP_200_OK
)
async def get_plan(
    plan_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("getPlan"))],
    runtime: Runtime,
) -> Plan:
    return await _service(ctx, runtime).get_plan(plan_id)


@router.post(
    "/plans/{plan_id}/versions",
    tags=["produits"],
    operation_id="createPlanVersion",
    status_code=status.HTTP_201_CREATED,
)
async def create_plan_version(
    plan_id: UUID,
    body: CreatePlanVersionRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createPlanVersion"))],
    runtime: Runtime,
) -> PlanVersion:
    return await _service(ctx, runtime).create_plan_version(plan_id, body)


@router.get(
    "/plan-versions/{plan_version_id}",
    tags=["produits"],
    operation_id="getPlanVersion",
    status_code=status.HTTP_200_OK,
)
async def get_plan_version(
    plan_version_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("getPlanVersion"))],
    runtime: Runtime,
) -> PlanVersion:
    return await _service(ctx, runtime).get_plan_version(plan_version_id)


@router.post(
    "/plan-versions/{plan_version_id}/publication",
    tags=["produits"],
    operation_id="publishPlanVersion",
    status_code=status.HTTP_200_OK,
)
async def publish_plan_version(
    plan_version_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("publishPlanVersion"))],
    runtime: Runtime,
) -> PlanVersion:
    return await _service(ctx, runtime).publish_plan_version(plan_version_id)


# --- Réseau ------------------------------------------------------------------------------------


@router.get(
    "/providers", tags=["produits"], operation_id="listProviders", status_code=status.HTTP_200_OK
)
async def list_providers(
    ctx: Annotated[RequestContext, Depends(require_operation("listProviders"))],
    runtime: Runtime,
    at: AtDate = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ProviderList:
    return await _service(ctx, runtime).list_providers(at, cursor, limit)


@router.post(
    "/providers",
    tags=["produits"],
    operation_id="createProvider",
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    body: CreateProviderRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createProvider"))],
    runtime: Runtime,
) -> Provider:
    return await _service(ctx, runtime).create_provider(body)


@router.get(
    "/providers/{provider_id}",
    tags=["produits"],
    operation_id="getProvider",
    status_code=status.HTTP_200_OK,
)
async def get_provider(
    provider_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("getProvider"))],
    runtime: Runtime,
) -> Provider:
    return await _service(ctx, runtime).get_provider(provider_id)


@router.post(
    "/providers/{provider_id}/conventions",
    tags=["produits"],
    operation_id="createProviderConvention",
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_convention(
    provider_id: UUID,
    body: CreateProviderConventionRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createProviderConvention"))],
    runtime: Runtime,
) -> ProviderConvention:
    return await _service(ctx, runtime).create_convention(provider_id, body)


# --- Nomenclature et barème --------------------------------------------------------------------


@router.get(
    "/tariffs", tags=["produits"], operation_id="listTariffs", status_code=status.HTTP_200_OK
)
async def list_tariffs(
    ctx: Annotated[RequestContext, Depends(require_operation("listTariffs"))],
    runtime: Runtime,
    at: AtDate = None,
) -> TariffList:
    return await _service(ctx, runtime).list_tariffs(at)


@router.get("/acts", tags=["produits"], operation_id="listActs", status_code=status.HTTP_200_OK)
async def list_acts(
    ctx: Annotated[RequestContext, Depends(require_operation("listActs"))], runtime: Runtime
) -> ActList:
    return await _service(ctx, runtime).list_acts()


@router.post(
    "/acts", tags=["produits"], operation_id="createAct", status_code=status.HTTP_201_CREATED
)
async def create_act(
    body: CreateActRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createAct"))],
    runtime: Runtime,
) -> Act:
    return await _service(ctx, runtime).create_act(body)


@router.post(
    "/acts/{act_id}/tariffs",
    tags=["produits"],
    operation_id="createTariffItem",
    status_code=status.HTTP_201_CREATED,
)
async def create_tariff_item(
    act_id: UUID,
    body: CreateTariffItemRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createTariffItem"))],
    runtime: Runtime,
) -> TariffItem:
    return await _service(ctx, runtime).create_tariff(act_id, body)


# --- Règles ------------------------------------------------------------------------------------


@router.get("/rules", tags=["regles"], operation_id="listRules", status_code=status.HTTP_200_OK)
async def list_rules(
    ctx: Annotated[RequestContext, Depends(require_operation("listRules"))], runtime: Runtime
) -> RuleList:
    return await _service(ctx, runtime).list_rules()


# Déclarée avant ``/rules/{rule_code}/...`` par lisibilité ; chemins distincts de toute façon.
@router.post(
    "/rules/evaluation",
    tags=["regles"],
    operation_id="evaluateRules",
    status_code=status.HTTP_200_OK,
)
async def evaluate_rules(
    body: EvaluateRulesRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("evaluateRules"))],
    runtime: Runtime,
) -> Decision:
    return await _service(ctx, runtime).evaluate(body)


@router.get(
    "/rules/{rule_code}/versions",
    tags=["regles"],
    operation_id="listRuleVersions",
    status_code=status.HTTP_200_OK,
)
async def list_rule_versions(
    rule_code: RuleCode,
    ctx: Annotated[RequestContext, Depends(require_operation("listRuleVersions"))],
    runtime: Runtime,
) -> RuleVersionList:
    return await _service(ctx, runtime).list_rule_versions(rule_code)


@router.post(
    "/rules/{rule_code}/versions",
    tags=["regles"],
    operation_id="createRuleVersion",
    status_code=status.HTTP_201_CREATED,
)
async def create_rule_version(
    rule_code: RuleCode,
    body: CreateRuleVersionRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createRuleVersion"))],
    runtime: Runtime,
) -> RuleVersion:
    return await _service(ctx, runtime).create_rule_version(rule_code, body)


@router.post(
    "/rule-versions/{rule_version_id}/publication",
    tags=["regles"],
    operation_id="publishRuleVersion",
    status_code=status.HTTP_200_OK,
)
async def publish_rule_version(
    rule_version_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("publishRuleVersion"))],
    runtime: Runtime,
) -> RuleVersion:
    return await _service(ctx, runtime).publish_rule_version(rule_version_id)


# --- Erreurs -----------------------------------------------------------------------------------


async def rules_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """``RulesError`` → ``application/problem+json`` (code stable, message, action)."""
    if not isinstance(exc, RulesError):  # pragma: no cover — enregistré pour RulesError seul
        raise exc
    request_id = request_id_of(request)
    if exc.http_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        log_event(logger, logging.ERROR, "rules.error", code=exc.code, request_id=request_id)
    return JSONResponse(
        status_code=exc.http_status,
        media_type=PROBLEM_JSON,
        headers={REQUEST_ID_HEADER: request_id},
        content={
            "code": exc.code,
            "message": exc.message,
            "action": exc.action,
            "request_id": request_id,
        },
    )


def install(app: FastAPI, runtime: RulesRuntime) -> None:
    """Monte les routes L2 et le rendu problem+json de leurs erreurs métier."""
    setattr(app.state, STATE_KEY, runtime)
    app.include_router(router)
    app.add_exception_handler(RulesError, rules_error_handler)
