"""R9 et R6 — client FHIR HealthOS contre un serveur simulé.

* Seul l'identifiant pseudonyme part vers HealthOS, jamais le nom, le téléphone ni la date de
  naissance ; ce qui revient d'identifiant n'est pas remonté à l'appelant.
* La consultation ne renvoie pas le motif ; le motif ne se lit qu'avec un audit préalable.
* Toutes les requêtes du test passent sous la garde d'egress (liste blanche du test).

Données entièrement fictives.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from collections.abc import Iterator
from dataclasses import asdict, fields
from datetime import UTC, datetime

import pytest

from api.integrations.egress import EgressAllowlist, EgressDeniedError, Endpoint, egress_guard
from api.integrations.healthos import (
    MEDICAL_REASON_READ_ACTION,
    PSEUDONYM_SYSTEM,
    EncounterSummary,
    HealthOSClient,
    HealthOSNotFoundError,
    HealthOSUnavailableError,
    MedicalReasonRead,
    PatientLink,
    ReasonReadAuditEvent,
    ReasonReadContext,
)
from api.integrations.healthos_sim import SimulatedHealthOS
from api.integrations.transport import GuardedHttpTransport

# Personne fictive : ces valeurs ne doivent JAMAIS apparaître dans une requête sortante.
GIVEN_NAME = "Adjoua"
FAMILY_NAME = "Tanoh-Fictive"
PHONE = "+2250700000001"
BIRTH_DATE = "1987-03-14"
PSEUDONYM = uuid.UUID("5f0c2a9e-3b7d-4c1e-9a55-0d6b8e2f4a11")
ENCOUNTER_REF = "enc-7d1f"
REASON_TEXT = "Motif fictif de test — ne doit jamais être journalisé"
ORG_ID = uuid.UUID("00000000-0000-4000-8000-00000000000a")
CLAIM_ID = uuid.UUID("00000000-0000-4000-8000-0000000000c1")
USER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000d1")


class RecordingAudit:
    """Hook d'audit de test : reproduit le rôle de L1 (insertion dans ``audit_events``)."""

    def __init__(self, *, fail: bool = False) -> None:
        self.events: list[ReasonReadAuditEvent] = []
        self.fail = fail

    async def __call__(self, event: ReasonReadAuditEvent) -> uuid.UUID:
        if self.fail:
            raise RuntimeError("base d'audit indisponible")
        self.events.append(event)
        return uuid.uuid4()


@pytest.fixture
def sim() -> Iterator[SimulatedHealthOS]:
    with SimulatedHealthOS() as server:
        server.add_patient(
            pseudonym=PSEUDONYM,
            healthos_id="pat-001",
            given_name=GIVEN_NAME,
            family_name=FAMILY_NAME,
            phone=PHONE,
            birth_date=BIRTH_DATE,
        )
        server.add_encounter(
            ref=ENCOUNTER_REF,
            pseudonym=PSEUDONYM,
            status="finished",
            start="2026-09-20T09:30:00Z",
            facility_ref="Organization/fac-12",
            reason=REASON_TEXT,
        )
        yield server


@pytest.fixture
def client(sim: SimulatedHealthOS) -> Iterator[HealthOSClient]:
    allowlist = EgressAllowlist(frozenset({Endpoint("127.0.0.1", sim.port)}))
    with egress_guard(allowlist):
        yield HealthOSClient(
            base_url=sim.fhir_base_url,
            transport=GuardedHttpTransport(allowlist, timeout_seconds=2),
        )


def _context() -> ReasonReadContext:
    return ReasonReadContext(
        organization_id=ORG_ID,
        claim_id=CLAIM_ID,
        actor_user_id=USER_ID,
        actor_role="medecin_conseil",
        request_id="req_test_01",
    )


def _everything_sent(sim: SimulatedHealthOS) -> str:
    return json.dumps([r.as_dict() for r in sim.requests])


# --- Identité ---------------------------------------------------------------------------------


def test_resolve_patient_sends_only_the_pseudonym(
    client: HealthOSClient, sim: SimulatedHealthOS
) -> None:
    link = asyncio.run(client.resolve_patient(PSEUDONYM))
    assert link == PatientLink(pseudonym=PSEUDONYM, healthos_patient_id="pat-001", active=True)
    sent = _everything_sent(sim)
    assert str(PSEUDONYM) in sent
    assert f"{PSEUDONYM_SYSTEM}|{PSEUDONYM}" in sim.requests[0].query_values("identifier")


def test_identity_returned_by_healthos_is_dropped(client: HealthOSClient) -> None:
    # Le simulateur renvoie nom, téléphone et date de naissance comme le FHIR HealthOS actuel.
    link = asyncio.run(client.resolve_patient(PSEUDONYM))
    dumped = json.dumps(asdict(link), default=str)
    for value in (GIVEN_NAME, FAMILY_NAME, PHONE, BIRTH_DATE):
        assert value not in dumped
    assert {f.name for f in fields(PatientLink)} == {"pseudonym", "healthos_patient_id", "active"}


def test_unknown_pseudonym_is_not_found(client: HealthOSClient) -> None:
    with pytest.raises(HealthOSNotFoundError):
        asyncio.run(client.resolve_patient(uuid.uuid4()))


# --- Consultation -----------------------------------------------------------------------------


def test_encounter_summary_has_no_medical_reason(client: HealthOSClient) -> None:
    summary = asyncio.run(client.get_encounter(encounter_ref=ENCOUNTER_REF, pseudonym=PSEUDONYM))
    assert summary == EncounterSummary(
        ref=ENCOUNTER_REF,
        status="finished",
        started_at=datetime(2026, 9, 20, 9, 30, tzinfo=UTC),
        facility_ref="Organization/fac-12",
    )
    assert REASON_TEXT not in json.dumps(asdict(summary), default=str)
    assert {f.name for f in fields(EncounterSummary)} == {
        "ref",
        "status",
        "started_at",
        "facility_ref",
    }


def test_encounter_is_scoped_to_the_pseudonym(
    client: HealthOSClient, sim: SimulatedHealthOS
) -> None:
    with pytest.raises(HealthOSNotFoundError):
        asyncio.run(client.get_encounter(encounter_ref=ENCOUNTER_REF, pseudonym=uuid.uuid4()))
    assert f"{PSEUDONYM_SYSTEM}|" in sim.requests[-1].query_values("subject:identifier")[0]


# --- Motif à la demande, audit préalable ------------------------------------------------------


def test_reason_read_records_audit_before_calling_healthos(
    client: HealthOSClient, sim: SimulatedHealthOS
) -> None:
    audit = RecordingAudit()
    result = asyncio.run(
        client.read_medical_reason(
            encounter_ref=ENCOUNTER_REF,
            pseudonym=PSEUDONYM,
            context=_context(),
            record_audit=audit,
        )
    )
    assert isinstance(result, MedicalReasonRead)
    assert result.text == REASON_TEXT
    assert result.source == "healthos"
    assert result.claim_id == CLAIM_ID
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event.action == MEDICAL_REASON_READ_ACTION == "claim.medical_reason.read"
    assert event.target_type == "claim"
    assert event.target_id == CLAIM_ID
    assert event.organization_id == ORG_ID
    # Métadonnées : identifiants pseudonymes seulement, jamais le motif.
    assert REASON_TEXT not in json.dumps(event.metadata)
    assert event.metadata == {"healthos_encounter_ref": ENCOUNTER_REF}


def test_each_read_creates_its_own_audit_event(client: HealthOSClient) -> None:
    audit = RecordingAudit()
    for _ in range(3):
        asyncio.run(
            client.read_medical_reason(
                encounter_ref=ENCOUNTER_REF,
                pseudonym=PSEUDONYM,
                context=_context(),
                record_audit=audit,
            )
        )
    assert len(audit.events) == 3


def test_no_audit_no_read(client: HealthOSClient, sim: SimulatedHealthOS) -> None:
    with pytest.raises(RuntimeError, match="audit"):
        asyncio.run(
            client.read_medical_reason(
                encounter_ref=ENCOUNTER_REF,
                pseudonym=PSEUDONYM,
                context=_context(),
                record_audit=RecordingAudit(fail=True),
            )
        )
    assert sim.requests == [], "HealthOS ne doit pas être appelé si l'audit échoue"


def test_record_audit_is_mandatory() -> None:
    parameter = inspect.signature(HealthOSClient.read_medical_reason).parameters["record_audit"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_reason_is_never_logged(client: HealthOSClient, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    asyncio.run(
        client.read_medical_reason(
            encounter_ref=ENCOUNTER_REF,
            pseudonym=PSEUDONYM,
            context=_context(),
            record_audit=RecordingAudit(),
        )
    )
    assert REASON_TEXT not in caplog.text


# --- Aucune donnée identifiante sortante, sur tout le parcours --------------------------------


def test_full_journey_never_sends_identifying_data(
    client: HealthOSClient, sim: SimulatedHealthOS
) -> None:
    asyncio.run(client.resolve_patient(PSEUDONYM))
    asyncio.run(client.get_encounter(encounter_ref=ENCOUNTER_REF, pseudonym=PSEUDONYM))
    asyncio.run(
        client.read_medical_reason(
            encounter_ref=ENCOUNTER_REF,
            pseudonym=PSEUDONYM,
            context=_context(),
            record_audit=RecordingAudit(),
        )
    )
    assert len(sim.requests) == 3
    sent = _everything_sent(sim)
    for value in (GIVEN_NAME, FAMILY_NAME, PHONE, BIRTH_DATE, str(ORG_ID), str(USER_ID)):
        assert value not in sent, f"donnée identifiante envoyée : {value}"
    assert all(r.method == "GET" and not r.body for r in sim.requests)


def test_client_api_accepts_no_identity_fields() -> None:
    identifying = ("name", "phone", "birth", "person", "member", "telecom", "address")
    for attr in ("resolve_patient", "get_encounter", "read_medical_reason"):
        params = inspect.signature(getattr(HealthOSClient, attr)).parameters
        for name in params:
            assert not any(word in name for word in identifying), f"{attr}({name})"
        assert params["pseudonym"].annotation in ("UUID", uuid.UUID)


# --- Pannes : INT-01, et la garde n'est jamais masquée ----------------------------------------


def test_upstream_error_maps_to_int_01(client: HealthOSClient, sim: SimulatedHealthOS) -> None:
    sim.fail_with = 503
    with pytest.raises(HealthOSUnavailableError) as caught:
        asyncio.run(client.resolve_patient(PSEUDONYM))
    assert caught.value.code == "INT-01"


def test_unreachable_healthos_maps_to_int_01() -> None:
    with SimulatedHealthOS() as sim:
        port = sim.port
    allowlist = EgressAllowlist(frozenset({Endpoint("127.0.0.1", port)}))
    closed = HealthOSClient(
        base_url=f"http://127.0.0.1:{port}/api/v1/fhir/R4",
        transport=GuardedHttpTransport(allowlist, timeout_seconds=1),
    )
    with pytest.raises(HealthOSUnavailableError):
        asyncio.run(closed.resolve_patient(PSEUDONYM))


def test_egress_denial_is_not_disguised_as_unavailable(sim: SimulatedHealthOS) -> None:
    empty = EgressAllowlist(frozenset())
    blocked = HealthOSClient(
        base_url=sim.fhir_base_url,
        transport=GuardedHttpTransport(empty, timeout_seconds=1),
    )
    with pytest.raises(EgressDeniedError):
        asyncio.run(blocked.resolve_patient(PSEUDONYM))
    assert sim.requests == []


def test_client_refuses_plain_http_outside_loopback() -> None:
    allowlist = EgressAllowlist(frozenset({Endpoint("healthos.ci.example", 80)}))
    with pytest.raises(ValueError, match="https"):
        HealthOSClient(
            base_url="http://healthos.ci.example/api/v1/fhir/R4",
            transport=GuardedHttpTransport(allowlist, timeout_seconds=1),
        )
