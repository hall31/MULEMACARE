"""Routes P3 « marque blanche » (tag ``marque-blanche``) : route → service → dépôt.

``getOrganizationBranding`` est public (``security: []``) : aucune organisation du jeton, la
marque est résolue par identifiant public ou domaine prouvé via la fonction du contrat. Les
réglages et la preuve de domaine (``verifyBrandingDomain``, CR-P3-02) sont réservés à l'admin
d'organisation (``require_operation``). Montage : ``install(app, BrandingRuntime(...))`` par
``create_app``.
"""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI, Query, Request, status

from api.branding.schemas import BrandingSettings, OrganizationBranding, UpdateBrandingRequest
from api.branding.service import BrandingRuntime, BrandingService
from api.core.context import RequestContext, get_database, require_operation
from api.core.database import Database

STATE_KEY: Final = "p3_branding"
SLUG_PATTERN: Final = r"^[a-z0-9][a-z0-9-]{1,62}$"


def get_service(request: Request) -> BrandingService:
    runtime = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(runtime, BrandingRuntime):  # pragma: no cover — installé par create_app
        msg = "module de marque blanche (P3) non installé"
        raise TypeError(msg)
    return BrandingService(runtime)


Service = Annotated[BrandingService, Depends(get_service)]
DatabaseDep = Annotated[Database, Depends(get_database)]
Slug = Annotated[
    str | None, Query(pattern=SLUG_PATTERN, description="Identifiant public de l'organisation.")
]
Domain = Annotated[
    str | None, Query(min_length=4, max_length=253, description="Domaine personnalisé.")
]

router = APIRouter(prefix="/v1", tags=["marque-blanche"])


@router.get(
    "/public/branding",
    operation_id="getOrganizationBranding",
    status_code=status.HTTP_200_OK,
)
async def get_organization_branding(
    service: Service, database: DatabaseDep, slug: Slug = None, domain: Domain = None
) -> OrganizationBranding:
    return await service.public(database, slug, domain)


@router.get(
    "/organization/branding",
    operation_id="getBrandingSettings",
    status_code=status.HTTP_200_OK,
)
async def get_branding_settings(
    ctx: Annotated[RequestContext, Depends(require_operation("getBrandingSettings"))],
    service: Service,
) -> BrandingSettings:
    return await service.settings(ctx)


@router.put(
    "/organization/branding",
    operation_id="updateBrandingSettings",
    status_code=status.HTTP_200_OK,
)
async def update_branding_settings(
    body: UpdateBrandingRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("updateBrandingSettings"))],
    service: Service,
) -> BrandingSettings:
    return await service.update(ctx, body)


@router.post(
    "/organization/branding/domain-verification",
    operation_id="verifyBrandingDomain",
    status_code=status.HTTP_200_OK,
)
async def verify_branding_domain(
    ctx: Annotated[RequestContext, Depends(require_operation("verifyBrandingDomain"))],
    service: Service,
) -> BrandingSettings:
    return await service.verify_domain(ctx)


def install(app: FastAPI, runtime: BrandingRuntime) -> None:
    setattr(app.state, STATE_KEY, runtime)
    app.include_router(router)
