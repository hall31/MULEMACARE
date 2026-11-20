"""Routes L5 (tags « comptoir » et « prises-en-charge ») : route → service → dépôt.

L'organisation et les rôles viennent du jeton (``require_operation``, L1), jamais du client.
Montage : ``install(app, runtime)`` ajoute le routeur, le gestionnaire d'erreurs L5 et les
ports (HealthOS, QR, SMS, score de fraude, horloge).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from api.claims.errors import ClaimsError, claims_error_handler, problem
from api.claims.identification import IdentificationService
from api.claims.offline import OfflineService
from api.claims.ports import ClaimsRuntime
from api.claims.schemas import (
    ClaimCreated,
    ClaimDetail,
    ClaimList,
    ClaimStatus,
    CodeSent,
    CodeVerificationRequest,
    CounterDevice,
    CreateClaimRequest,
    DecideClaimRequest,
    Identification,
    MedicalReason,
    OfflinePolicy,
    OfflineSyncRequest,
    OfflineSyncResult,
    PhotoConfirmationRequest,
    RegisterCounterDeviceRequest,
    StartIdentificationRequest,
    SubmitClaimDocumentsRequest,
    WorkQueue,
)
from api.claims.service import ClaimsService
from api.core.context import RequestContext, require_operation
from api.core.medical import MEDICAL_REASON_RESPONSE_HEADERS

router = APIRouter(prefix="/v1")


def get_runtime(request: Request) -> ClaimsRuntime:
    runtime: ClaimsRuntime = request.app.state.claims_runtime
    return runtime


Runtime = Annotated[ClaimsRuntime, Depends(get_runtime)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]


def _replay(status_code: int, body: Any) -> JSONResponse:  # noqa: ANN401
    return JSONResponse(body, status_code=status_code)


# --- Comptoir ----------------------------------------------------------------------------------


@router.post(
    "/counter/identifications",
    operation_id="startIdentification",
    tags=["comptoir"],
    status_code=status.HTTP_201_CREATED,
)
async def start_identification(
    body: StartIdentificationRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("startIdentification"))],
    runtime: Runtime,
) -> Identification:
    return await IdentificationService(ctx, runtime).start(body)


@router.post(
    "/counter/identifications/{identification_id}/photo-confirmation",
    operation_id="confirmPhoto",
    tags=["comptoir"],
)
async def confirm_photo(
    identification_id: UUID,
    body: PhotoConfirmationRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("confirmPhoto"))],
    runtime: Runtime,
) -> Identification:
    return await IdentificationService(ctx, runtime).confirm_photo(
        identification_id, confirmed=body.confirmed
    )


@router.post(
    "/counter/identifications/{identification_id}/code",
    operation_id="sendIdentificationCode",
    tags=["comptoir"],
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_identification_code(
    identification_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("sendIdentificationCode"))],
    runtime: Runtime,
) -> CodeSent:
    return await IdentificationService(ctx, runtime).send_code(identification_id)


@router.post(
    "/counter/identifications/{identification_id}/code-verification",
    operation_id="verifyIdentificationCode",
    tags=["comptoir"],
    response_model=Identification,
)
async def verify_identification_code(
    identification_id: UUID,
    body: CodeVerificationRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("verifyIdentificationCode"))],
    runtime: Runtime,
) -> Identification | Response:
    outcome = await IdentificationService(ctx, runtime).verify_code(identification_id, body.code)
    if isinstance(outcome, ClaimsError):
        # Code faux ou blocage : réponse d'erreur, mais compteur et blocage VALIDÉS.
        return problem(outcome, ctx.request_id)
    return outcome


@router.get("/counter/offline-policy", operation_id="getOfflinePolicy", tags=["comptoir"])
async def get_offline_policy(
    ctx: Annotated[RequestContext, Depends(require_operation("getOfflinePolicy"))], runtime: Runtime
) -> OfflinePolicy:
    return await OfflineService(ctx, runtime).policy()


@router.post(
    "/counter/devices",
    operation_id="registerCounterDevice",
    tags=["comptoir"],
    status_code=status.HTTP_201_CREATED,
)
async def register_counter_device(
    body: RegisterCounterDeviceRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("registerCounterDevice"))],
    runtime: Runtime,
) -> CounterDevice:
    return await OfflineService(ctx, runtime).register_device(body)


@router.post(
    "/authorizations/offline-sync", operation_id="syncOfflineAuthorizations", tags=["comptoir"]
)
async def sync_offline_authorizations(
    body: OfflineSyncRequest,
    ctx: Annotated[RequestContext, Depends(require_operation("syncOfflineAuthorizations"))],
    runtime: Runtime,
) -> OfflineSyncResult:
    return await OfflineService(ctx, runtime).sync(body)


# --- Prises en charge --------------------------------------------------------------------------


@router.get("/claims", operation_id="listClaims", tags=["prises-en-charge"])
async def list_claims(  # noqa: PLR0913 — filtres du contrat
    *,
    ctx: Annotated[RequestContext, Depends(require_operation("listClaims"))],
    runtime: Runtime,
    claim_status: Annotated[ClaimStatus | None, Query(alias="status")] = None,
    fraud_flagged: bool | None = None,
    member_id: UUID | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ClaimList:
    return await ClaimsService(ctx, runtime).list(
        status=claim_status,
        fraud_flagged=fraud_flagged,
        member_id=member_id,
        date_from=date_from,
        date_to=date_to,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/claims",
    operation_id="createClaim",
    tags=["prises-en-charge"],
    status_code=status.HTTP_201_CREATED,
    response_model=ClaimCreated,
)
async def create_claim(
    body: CreateClaimRequest,
    idempotency_key: IdempotencyKey,
    ctx: Annotated[RequestContext, Depends(require_operation("createClaim"))],
    runtime: Runtime,
) -> JSONResponse:
    return _replay(*await ClaimsService(ctx, runtime).create(body, idempotency_key))


@router.get("/claims/{claim_id}", operation_id="getClaim", tags=["prises-en-charge"])
async def get_claim(
    claim_id: UUID,
    ctx: Annotated[RequestContext, Depends(require_operation("getClaim"))],
    runtime: Runtime,
) -> ClaimDetail:
    return await ClaimsService(ctx, runtime).get(claim_id)


@router.post(
    "/claims/{claim_id}/decisions",
    operation_id="decideClaim",
    tags=["prises-en-charge"],
    response_model=ClaimDetail,
)
async def decide_claim(
    claim_id: UUID,
    body: DecideClaimRequest,
    idempotency_key: IdempotencyKey,
    ctx: Annotated[RequestContext, Depends(require_operation("decideClaim"))],
    runtime: Runtime,
) -> JSONResponse:
    return _replay(*await ClaimsService(ctx, runtime).decide(claim_id, body, idempotency_key))


@router.post(
    "/claims/{claim_id}/documents",
    operation_id="submitClaimDocuments",
    tags=["prises-en-charge"],
    response_model=ClaimDetail,
)
async def submit_claim_documents(
    claim_id: UUID,
    body: SubmitClaimDocumentsRequest,
    idempotency_key: IdempotencyKey,
    ctx: Annotated[RequestContext, Depends(require_operation("submitClaimDocuments"))],
    runtime: Runtime,
) -> JSONResponse:
    service = ClaimsService(ctx, runtime)
    return _replay(*await service.submit_documents(claim_id, body, idempotency_key))


@router.get(
    "/claims/{claim_id}/medical-reason",
    operation_id="readMedicalReason",
    tags=["prises-en-charge"],
)
async def read_medical_reason(
    claim_id: UUID,
    response: Response,
    ctx: Annotated[RequestContext, Depends(require_operation("readMedicalReason"))],
    runtime: Runtime,
) -> MedicalReason:
    result = await ClaimsService(ctx, runtime).read_medical_reason(claim_id)
    response.headers.update(MEDICAL_REASON_RESPONSE_HEADERS)
    return result


@router.get("/work-queue", operation_id="getWorkQueue", tags=["prises-en-charge"])
async def get_work_queue(
    ctx: Annotated[RequestContext, Depends(require_operation("getWorkQueue"))], runtime: Runtime
) -> WorkQueue:
    return await ClaimsService(ctx, runtime).work_queue()


def install(app: FastAPI, runtime: ClaimsRuntime) -> None:
    """Monte les routes L5, la conversion des erreurs L5 en problem+json et les ports."""
    app.state.claims_runtime = runtime
    app.include_router(router)
    app.add_exception_handler(ClaimsError, claims_error_handler)
