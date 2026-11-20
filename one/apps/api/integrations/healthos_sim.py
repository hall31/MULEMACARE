"""Serveur HealthOS simulé (FHIR R4 minimal) pour les tests de L9 et de L5.

Il écoute sur ``127.0.0.1`` (port choisi par le système), enregistre chaque requête reçue et
répond comme le ferait le pire serveur réaliste : la ressource ``Patient`` contient nom,
téléphone et date de naissance (comme le FHIR HealthOS actuel), l'``Encounter`` contient
toujours son motif (``reasonCode``). C'est au client de n'en rien garder.

Contrat simulé (à confirmer côté HealthOS, PRD §10 Q6) :

* ``GET {base}/metadata``
* ``GET {base}/Patient?identifier=urn:mulemacare:pseudonym|<uuid>`` → ``Bundle``
* ``GET {base}/Encounter?_id=<ref>&subject:identifier=urn:mulemacare:pseudonym|<uuid>``
  → ``Bundle``

Données exclusivement fictives, fournies par le test.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self
from urllib.parse import parse_qs, urlsplit

from api.integrations.healthos import FHIR_JSON, PSEUDONYM_SYSTEM

FHIR_BASE_PATH = "/api/v1/fhir/R4"


@dataclass(frozen=True, slots=True)
class RecordedRequest:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    body: bytes

    def query_values(self, name: str) -> list[str]:
        return self.query.get(name, [])

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "path": self.path,
            "query": self.query,
            "headers": self.headers,
            "body": self.body.decode("utf-8", errors="replace"),
        }


@dataclass(slots=True)
class _Patient:
    healthos_id: str
    resource: dict[str, Any]


@dataclass(slots=True)
class _Encounter:
    pseudonym: uuid.UUID
    resource: dict[str, Any]


@dataclass(slots=True)
class _State:
    patients: dict[uuid.UUID, _Patient] = field(default_factory=dict)
    encounters: dict[str, _Encounter] = field(default_factory=dict)
    requests: list[RecordedRequest] = field(default_factory=list)
    fail_with: int | None = None
    redirect_to: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


def _bundle(resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(resources),
        "entry": [{"resource": r} for r in resources],
    }


def _pseudonym_from(token: str | None) -> uuid.UUID | None:
    if not token:
        return None
    system, _, value = token.partition("|")
    if system != PSEUDONYM_SYSTEM:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


class _Handler(BaseHTTPRequestHandler):
    server: _SimServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: ANN401
        """Silencieux : les journaux du simulateur n'ont rien à apprendre aux tests."""

    def do_GET(self) -> None:
        state = self.server.state
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        with state.lock:
            state.requests.append(
                RecordedRequest("GET", parts.path, query, dict(self.headers.items()), body)
            )
            fail_with, redirect_to = state.fail_with, state.redirect_to
        if fail_with is not None:
            self._send(fail_with, {"resourceType": "OperationOutcome"})
            return
        if redirect_to is not None:
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", redirect_to)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        route = parts.path.removeprefix(FHIR_BASE_PATH)
        if route == "/metadata":
            self._send(
                HTTPStatus.OK, {"resourceType": "CapabilityStatement", "fhirVersion": "4.0.1"}
            )
        elif route == "/Patient":
            self._send(HTTPStatus.OK, _bundle(self._patients(query)))
        elif route == "/Encounter":
            self._send(HTTPStatus.OK, _bundle(self._encounters(query)))
        else:
            self._send(HTTPStatus.NOT_FOUND, {"resourceType": "OperationOutcome"})

    def _patients(self, query: dict[str, list[str]]) -> list[dict[str, Any]]:
        pseudonym = _pseudonym_from(next(iter(query.get("identifier", [])), None))
        patient = self.server.state.patients.get(pseudonym) if pseudonym else None
        return [patient.resource] if patient else []

    def _encounters(self, query: dict[str, list[str]]) -> list[dict[str, Any]]:
        ref = (query.get("_id") or [""])[0]
        pseudonym = _pseudonym_from(next(iter(query.get("subject:identifier", [])), None))
        encounter = self.server.state.encounters.get(ref)
        if encounter is None or pseudonym != encounter.pseudonym:
            return []
        return [encounter.resource]

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", FHIR_JSON)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class _SimServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, state: _State) -> None:
        self.state = state
        super().__init__(("127.0.0.1", 0), _Handler)


class SimulatedHealthOS:
    """Serveur FHIR simulé, utilisable comme gestionnaire de contexte."""

    def __init__(self) -> None:
        self._state = _State()
        self._server: _SimServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 0

    # --- cycle de vie -------------------------------------------------------------------

    def __enter__(self) -> Self:
        self._server = _SimServer(self._state)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(
            target=self._server.serve_forever, args=(0.05,), daemon=True
        )
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def fhir_base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}{FHIR_BASE_PATH}"

    # --- observation et pannes ----------------------------------------------------------

    @property
    def requests(self) -> list[RecordedRequest]:
        with self._state.lock:
            return list(self._state.requests)

    @property
    def fail_with(self) -> int | None:
        return self._state.fail_with

    @fail_with.setter
    def fail_with(self, status: int | None) -> None:
        self._state.fail_with = status

    @property
    def redirect_to(self) -> str | None:
        return self._state.redirect_to

    @redirect_to.setter
    def redirect_to(self, url: str | None) -> None:
        self._state.redirect_to = url

    # --- données fictives ---------------------------------------------------------------

    def add_patient(  # noqa: PLR0913 — ressource FHIR complète, volontairement identifiante
        self,
        *,
        pseudonym: uuid.UUID,
        healthos_id: str,
        given_name: str,
        family_name: str,
        phone: str,
        birth_date: str,
    ) -> None:
        self._state.patients[pseudonym] = _Patient(
            healthos_id=healthos_id,
            resource={
                "resourceType": "Patient",
                "id": healthos_id,
                "active": True,
                "identifier": [{"system": PSEUDONYM_SYSTEM, "value": str(pseudonym)}],
                "name": [{"use": "official", "family": family_name, "given": [given_name]}],
                "telecom": [{"system": "phone", "value": phone, "use": "mobile"}],
                "birthDate": birth_date,
            },
        )

    def add_encounter(  # noqa: PLR0913 — ressource FHIR complète
        self,
        *,
        ref: str,
        pseudonym: uuid.UUID,
        status: str,
        start: str,
        facility_ref: str,
        reason: str,
    ) -> None:
        patient = self._state.patients.get(pseudonym)
        subject = f"Patient/{patient.healthos_id}" if patient else "Patient/unknown"
        self._state.encounters[ref] = _Encounter(
            pseudonym=pseudonym,
            resource={
                "resourceType": "Encounter",
                "id": ref,
                "status": status,
                "subject": {"reference": subject},
                "period": {"start": start},
                "serviceProvider": {"reference": facility_ref},
                "reasonCode": [{"text": reason}],
            },
        )
