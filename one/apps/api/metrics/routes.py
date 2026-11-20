"""Routes P2 « mesure » (tag ``mesure``) : route → service → dépôt, aucune logique ici.

``recordProductEvent`` : tout rôle authentifié, pour ses propres écrans. ``getProductMetrics`` :
gestionnaire et admin (matrice du noyau, ``require_operation``). L'organisation vient du jeton.
Montage : ``install(app, MetricsRuntime(clock=...))`` par ``api.core.app.create_app``.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response, status

from api.core.context import RequestContext, require_operation
from api.metrics.runtime import MetricsRuntime
from api.metrics.schemas import ProductEventRequest, ProductMetrics
from api.metrics.service import MetricsService

STATE_KEY: Final = "p2_metrics"


def get_runtime(request: Request) -> MetricsRuntime:
    runtime = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(runtime, MetricsRuntime):  # pragma: no cover — installé par create_app
        msg = "module de mesure (P2) non installé"
        raise TypeError(msg)
    return runtime


Runtime = Annotated[MetricsRuntime, Depends(get_runtime)]
From = Annotated[date | None, Query(alias="from", description="Début de période (inclus).")]
To = Annotated[date | None, Query(alias="to", description="Fin de période (incluse).")]

router = APIRouter(prefix="/v1", tags=["mesure"])


@router.post(
    "/telemetry/events",
    operation_id="recordProductEvent",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def record_product_event(
    body: ProductEventRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("recordProductEvent"))],
    runtime: Runtime,
) -> Response:
    await MetricsService(ctx, runtime).record(body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/metrics/product", operation_id="getProductMetrics", status_code=status.HTTP_200_OK)
async def get_product_metrics(
    ctx: Annotated[RequestContext, Depends(require_operation("getProductMetrics"))],
    runtime: Runtime,
    start: From = None,
    end: To = None,
) -> ProductMetrics:
    return await MetricsService(ctx, runtime).product_metrics(start, end)


def install(app: FastAPI, runtime: MetricsRuntime) -> None:
    setattr(app.state, STATE_KEY, runtime)
    app.include_router(router)
