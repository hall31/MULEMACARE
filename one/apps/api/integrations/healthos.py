"""Client FHIR R4 minimal vers HealthOS (R9, R6) : identité, consultation, motif à la demande.

Invariants :

* **Seul l'identifiant pseudonyme part** (``persons.healthos_pseudonym``, système
  ``urn:mulemacare:pseudonym``). L'API du client n'accepte aucun champ d'identité ; les requêtes
  sont des ``GET`` sans corps.
* **Rien d'identifiant ni de clinique ne remonte en dehors de ce qui est demandé** : le nom, le
  téléphone et la date de naissance renvoyés par HealthOS sont ignorés ; la consultation est
  rendue sans motif.
* **Motif = audit d'abord.** ``read_medical_reason`` exige un hook d'audit (fourni par L1/L5,
  qui insère ``audit_events`` avec l'action ``claim.medical_reason.read``). Le hook est appelé
  avant la requête ; s'il échoue, HealthOS n'est pas appelé. Toute tentative est donc tracée,
  y compris celle que HealthOS n'aboutit pas à servir.
* **Aucune copie** : ce module n'a accès à aucune base et ne met rien en cache ; le motif est
  rendu à l'appelant, qui le renvoie avec ``Cache-Control: no-store`` sans le stocker.
* Pannes réseau et réponses inattendues → ``HealthOSUnavailableError`` (``INT-01``). Un refus
  d'egress (``EgressDeniedError``) n'est jamais déguisé en panne.
"""

from __future__ import annotations

import http.client
import json
import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlencode
from uuid import UUID

from api.core.jsonlog import LOGGER_NAME, log_event
from api.integrations.egress import EgressDeniedError
from api.integrations.transport import HttpRequest, HttpResponse, HttpTransport, split_destination

PSEUDONYM_SYSTEM = "urn:mulemacare:pseudonym"
MEDICAL_REASON_READ_ACTION = "claim.medical_reason.read"
FHIR_JSON = "application/fhir+json"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
# Identifiant logique FHIR (R4 : [A-Za-z0-9\-\.]{1,64}).
_FHIR_ID = re.compile(r"^[A-Za-z0-9\-.]{1,64}$")

logger = logging.getLogger(f"{LOGGER_NAME}.integrations.healthos")

RequestAuthenticator = Callable[[HttpRequest], Mapping[str, str]]
"""Produit les en-têtes d'authentification d'une requête (contrat HealthOS à définir)."""


# --- Erreurs -----------------------------------------------------------------------------------


class HealthOSError(Exception):
    code = "INT-01"


class HealthOSUnavailableError(HealthOSError):
    """HealthOS injoignable ou réponse inexploitable (``INT-01``, HTTP 502)."""

    code = "INT-01"


class HealthOSNotFoundError(HealthOSError):
    """Ressource absente ou hors du pseudonyme demandé (``NOT-01``, HTTP 404)."""

    code = "NOT-01"


# --- Résultats ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PatientLink:
    """Correspondance pseudonyme → patient HealthOS. Aucune donnée d'identité civile."""

    pseudonym: UUID
    healthos_patient_id: str
    active: bool


@dataclass(frozen=True, slots=True)
class EncounterSummary:
    """Consultation sans motif médical."""

    ref: str
    status: str
    started_at: datetime | None
    facility_ref: str | None


@dataclass(frozen=True, slots=True)
class MedicalReasonRead:
    """Réponse ``MedicalReason`` de l'OpenAPI. Le texte n'apparaît pas dans ``repr``."""

    claim_id: UUID
    text: str = field(repr=False)
    source: Literal["healthos"]
    read_at: datetime
    audit_event_id: UUID


# --- Hook d'audit (exposé à l'appelant) --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReasonReadContext:
    """Qui lit, pour quel dossier. Fourni par la route L5 depuis le jeton."""

    organization_id: UUID
    claim_id: UUID
    actor_user_id: UUID
    actor_role: str
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReasonReadAuditEvent:
    """Ligne ``audit_events`` à insérer (colonnes du contrat ``schema.sql``)."""

    organization_id: UUID
    actor_user_id: UUID
    actor_role: str
    action: str
    target_type: str
    target_id: UUID
    request_id: str | None
    metadata: Mapping[str, str]


ReasonReadAuditHook = Callable[[ReasonReadAuditEvent], Awaitable[UUID]]
"""Insère l'événement d'audit et renvoie ``audit_events.id``. Doit lever en cas d'échec."""


# --- Client ------------------------------------------------------------------------------------


class HealthOSClient:
    def __init__(
        self,
        *,
        base_url: str,
        transport: HttpTransport,
        authenticate: RequestAuthenticator | None = None,
    ) -> None:
        scheme, host, _, _ = split_destination(base_url)
        if scheme != "https" and host not in LOOPBACK_HOSTS:
            raise ValueError(f"HealthOS doit être joint en https hors boucle locale : {base_url}")
        self._base_url = base_url.rstrip("/")
        self._transport = transport
        self._authenticate = authenticate

    def with_base_url(self, base_url: str) -> HealthOSClient:
        """Même transport (donc même liste blanche), autre adresse."""
        return HealthOSClient(
            base_url=base_url, transport=self._transport, authenticate=self._authenticate
        )

    # --- identité ---------------------------------------------------------------------------

    async def resolve_patient(self, pseudonym: UUID) -> PatientLink:
        resource = await self._search_one(
            "Patient", {"identifier": _pseudonym_token(pseudonym), "_elements": "id,active"}
        )
        patient_id = resource.get("id")
        if not isinstance(patient_id, str):
            raise HealthOSUnavailableError("Patient sans identifiant")
        return PatientLink(
            pseudonym=pseudonym,
            healthos_patient_id=patient_id,
            active=bool(resource.get("active", True)),
        )

    # --- consultation -----------------------------------------------------------------------

    async def get_encounter(self, *, encounter_ref: str, pseudonym: UUID) -> EncounterSummary:
        resource = await self._search_encounter(
            encounter_ref, pseudonym, elements="id,status,period,serviceProvider"
        )
        period = resource.get("period")
        provider = resource.get("serviceProvider")
        start = period.get("start") if isinstance(period, dict) else None
        facility = provider.get("reference") if isinstance(provider, dict) else None
        return EncounterSummary(
            ref=encounter_ref,
            status=str(resource.get("status", "unknown")),
            started_at=_parse_instant(start),
            facility_ref=facility if isinstance(facility, str) else None,
        )

    # --- motif à la demande -----------------------------------------------------------------

    async def read_medical_reason(
        self,
        *,
        encounter_ref: str,
        pseudonym: UUID,
        context: ReasonReadContext,
        record_audit: ReasonReadAuditHook,
    ) -> MedicalReasonRead:
        _check_fhir_id(encounter_ref)
        audit_event_id = await record_audit(
            ReasonReadAuditEvent(
                organization_id=context.organization_id,
                actor_user_id=context.actor_user_id,
                actor_role=context.actor_role,
                action=MEDICAL_REASON_READ_ACTION,
                target_type="claim",
                target_id=context.claim_id,
                request_id=context.request_id,
                metadata={"healthos_encounter_ref": encounter_ref},
            )
        )
        resource = await self._search_encounter(encounter_ref, pseudonym, elements="id,reasonCode")
        text = _reason_text(resource)
        if text is None:
            raise HealthOSNotFoundError("consultation sans motif")
        return MedicalReasonRead(
            claim_id=context.claim_id,
            text=text,
            source="healthos",
            read_at=datetime.now(UTC),
            audit_event_id=audit_event_id,
        )

    # --- interne ----------------------------------------------------------------------------

    async def _search_encounter(
        self, encounter_ref: str, pseudonym: UUID, *, elements: str
    ) -> dict[str, Any]:
        _check_fhir_id(encounter_ref)
        return await self._search_one(
            "Encounter",
            {
                "_id": encounter_ref,
                "subject:identifier": _pseudonym_token(pseudonym),
                "_elements": elements,
            },
        )

    async def _search_one(self, resource_type: str, params: Mapping[str, str]) -> dict[str, Any]:
        bundle = await self._get_json(f"/{resource_type}", params)
        entries = bundle.get("entry") or []
        resources = [
            e["resource"]
            for e in entries
            if isinstance(e, dict)
            and isinstance(e.get("resource"), dict)
            and e["resource"].get("resourceType") == resource_type
        ]
        if not resources:
            raise HealthOSNotFoundError(f"{resource_type} introuvable")
        if len(resources) > 1:
            raise HealthOSUnavailableError(f"{resource_type} : réponse ambiguë")
        found: dict[str, Any] = resources[0]
        return found

    async def _get_json(self, path: str, params: Mapping[str, str]) -> dict[str, Any]:
        url = f"{self._base_url}{path}?{urlencode(params)}"
        headers = {"Accept": FHIR_JSON}
        if self._authenticate is not None:
            headers.update(self._authenticate(HttpRequest("GET", url, headers=headers)))
        request = HttpRequest("GET", url, headers=headers)
        response = await self._send(request, path)
        if response.status == http.HTTPStatus.NOT_FOUND:
            raise HealthOSNotFoundError(path)
        if response.status != http.HTTPStatus.OK:
            log_event(
                logger,
                logging.WARNING,
                "healthos.unexpected_status",
                path=path,
                status=response.status,
            )
            raise HealthOSUnavailableError(f"HealthOS a répondu {response.status}")
        try:
            payload = json.loads(response.body)
        except ValueError as exc:
            raise HealthOSUnavailableError("réponse HealthOS illisible") from exc
        if not isinstance(payload, dict):
            raise HealthOSUnavailableError("réponse HealthOS inattendue")
        return payload

    async def _send(self, request: HttpRequest, path: str) -> HttpResponse:
        try:
            return await self._transport.send(request)
        except EgressDeniedError:
            raise
        except (OSError, http.client.HTTPException) as exc:
            log_event(
                logger, logging.WARNING, "healthos.unreachable", path=path, error=type(exc).__name__
            )
            raise HealthOSUnavailableError("HealthOS injoignable") from exc


def _pseudonym_token(pseudonym: UUID) -> str:
    if not isinstance(pseudonym, UUID):
        raise TypeError("seul un pseudonyme UUID peut être transmis à HealthOS")
    return f"{PSEUDONYM_SYSTEM}|{pseudonym}"


def _check_fhir_id(value: str) -> None:
    if not _FHIR_ID.fullmatch(value):
        raise ValueError("référence de consultation HealthOS invalide")


def _parse_instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _reason_text(resource: Mapping[str, Any]) -> str | None:
    texts: list[str] = []
    for concept in resource.get("reasonCode") or []:
        if not isinstance(concept, dict):
            continue
        text = concept.get("text")
        if isinstance(text, str) and text:
            texts.append(text)
            continue
        for coding in concept.get("coding") or []:
            display = coding.get("display") if isinstance(coding, dict) else None
            if isinstance(display, str) and display:
                texts.append(display)
    return "; ".join(texts) if texts else None
