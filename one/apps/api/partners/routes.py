"""Routes P3 des espaces assureur, employeur et plateforme : route → service → dépôt.

Chaque route dépend de ``require_operation(<operationId>)`` (matrice du noyau) ; l'organisation
vient du jeton. Montage : ``install(app, PartnersRuntime(clock=...))`` par ``create_app``.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response, status

from api.core.context import RequestContext, require_operation
from api.partners.onboarding import PlatformService
from api.partners.schemas import (
    ConfigurationTemplate,
    ConfigurationTemplateList,
    CreateConfigurationTemplateRequest,
    CreateOrganizationRequest,
    EmployerConsumption,
    EmployerContractList,
    InsurerPortfolio,
    OrganizationOnboarding,
)
from api.partners.service import EmployerService, InsurerService, PartnersRuntime

STATE_KEY: Final = "p3_partners"
CSV_MEDIA_TYPE: Final = "text/csv; charset=utf-8"


def get_runtime(request: Request) -> PartnersRuntime:
    runtime = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(runtime, PartnersRuntime):  # pragma: no cover — installé par create_app
        msg = "module partenaires (P3) non installé"
        raise TypeError(msg)
    return runtime


Runtime = Annotated[PartnersRuntime, Depends(get_runtime)]
From = Annotated[date | None, Query(alias="from", description="Début de période (inclus).")]
To = Annotated[date | None, Query(alias="to", description="Fin de période (incluse).")]
WithinDays = Annotated[int, Query(ge=1, le=365, description="Horizon d'échéance, en jours.")]

router = APIRouter(prefix="/v1")


@router.get(
    "/insurer/portfolio",
    operation_id="getInsurerPortfolio",
    status_code=status.HTTP_200_OK,
    tags=["espace-assureur"],
)
async def get_insurer_portfolio(
    ctx: Annotated[RequestContext, Depends(require_operation("getInsurerPortfolio"))],
    runtime: Runtime,
    start: From = None,
    end: To = None,
) -> InsurerPortfolio:
    return await InsurerService(ctx, runtime).portfolio(start, end)


@router.get(
    "/insurer/portfolio/export",
    operation_id="exportInsurerPortfolio",
    status_code=status.HTTP_200_OK,
    response_class=Response,
    tags=["espace-assureur"],
)
async def export_insurer_portfolio(
    ctx: Annotated[RequestContext, Depends(require_operation("exportInsurerPortfolio"))],
    runtime: Runtime,
    start: From = None,
    end: To = None,
) -> Response:
    content = await InsurerService(ctx, runtime).export_csv(start, end)
    return Response(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="portefeuille-agrege.csv"',
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/employer/consumption",
    operation_id="getEmployerConsumption",
    status_code=status.HTTP_200_OK,
    tags=["espace-employeur"],
)
async def get_employer_consumption(
    ctx: Annotated[RequestContext, Depends(require_operation("getEmployerConsumption"))],
    runtime: Runtime,
    start: From = None,
    end: To = None,
) -> EmployerConsumption:
    return await EmployerService(ctx, runtime).consumption(start, end)


@router.get(
    "/employer/contracts",
    operation_id="listEmployerContracts",
    status_code=status.HTTP_200_OK,
    tags=["espace-employeur"],
)
async def list_employer_contracts(
    ctx: Annotated[RequestContext, Depends(require_operation("listEmployerContracts"))],
    runtime: Runtime,
    within_days: WithinDays = 90,
) -> EmployerContractList:
    return await EmployerService(ctx, runtime).contracts(within_days)


@router.post(
    "/platform/organizations",
    operation_id="createOrganization",
    status_code=status.HTTP_201_CREATED,
    tags=["plateforme"],
)
async def create_organization(
    body: CreateOrganizationRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createOrganization"))],
    runtime: Runtime,
) -> OrganizationOnboarding:
    return await PlatformService(ctx, runtime).create_organization(body)


@router.get(
    "/platform/configuration-templates",
    operation_id="listConfigurationTemplates",
    status_code=status.HTTP_200_OK,
    tags=["plateforme"],
)
async def list_configuration_templates(
    ctx: Annotated[RequestContext, Depends(require_operation("listConfigurationTemplates"))],
    runtime: Runtime,
) -> ConfigurationTemplateList:
    return await PlatformService(ctx, runtime).list_templates()


@router.post(
    "/platform/configuration-templates",
    operation_id="createConfigurationTemplate",
    status_code=status.HTTP_201_CREATED,
    tags=["plateforme"],
)
async def create_configuration_template(
    body: CreateConfigurationTemplateRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("createConfigurationTemplate"))],
    runtime: Runtime,
) -> ConfigurationTemplate:
    return await PlatformService(ctx, runtime).create_template(body)


def install(app: FastAPI, runtime: PartnersRuntime) -> None:
    setattr(app.state, STATE_KEY, runtime)
    app.include_router(router)
