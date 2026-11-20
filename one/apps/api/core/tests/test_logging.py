"""Logs JSON structurés, sans nom, téléphone, e-mail, sujet d'identité ni jeton."""

from __future__ import annotations

import io
import json
import logging
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.core.jsonlog import LOGGER_NAME, JsonFormatter, log_event
from api.core.tests.conftest import CoreSeed


@pytest.fixture
def captured() -> Iterator[io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    previous = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def _lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def test_chaque_ligne_est_du_json_avec_horodatage_utc(captured: io.StringIO) -> None:
    log_event(logging.getLogger(f"{LOGGER_NAME}.test"), logging.INFO, "test.event", count=3)
    (line,) = _lines(captured)
    assert line["event"] == "test.event"
    assert line["count"] == 3
    assert isinstance(line["ts"], str)
    assert line["ts"].endswith("Z")


@pytest.mark.parametrize(
    "key",
    [
        "name",
        "display_name",
        "given_name",
        "family_name",
        "phone",
        "phone_e164",
        "email",
        "idp_subject",
        "token",
        "card_number",
        "text",
        "motif",
    ],
)
def test_champs_identifiants_masques(captured: io.StringIO, key: str) -> None:
    log_event(logging.getLogger(LOGGER_NAME), logging.INFO, "test.pii", **{key: "Awa Fictive"})
    assert "Awa" not in captured.getvalue()


def test_exception_journalisee_sans_son_message(captured: io.StringIO) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    try:
        raise ValueError("Awa Fictive +2250700000000")
    except ValueError:
        logger.exception("test.failure")
    (line,) = _lines(captured)
    exception = line["exception"]
    assert isinstance(exception, dict)
    assert exception["type"] == "ValueError"
    assert "Awa" not in captured.getvalue()
    assert "2250700000000" not in captured.getvalue()


def test_requetes_journalisees_sans_donnee_identifiante(
    captured: io.StringIO, client: TestClient, core_seed: CoreSeed
) -> None:
    subject = f"awa.fictive.{uuid.uuid4().hex}@idp.invalid"
    response = client.post(
        "/v1/users",
        json={
            "idp_subject": subject,
            "display_name": "Awa Fictive Kouassi",
            "email": "awa.fictive@example.invalid",
            "roles": [{"role": "gestionnaire"}],
        },
        headers=core_seed.auth("a", "admin"),
    )
    assert response.status_code == 201
    output = captured.getvalue()
    lines = _lines(captured)
    assert any(line["event"] == "http.request" for line in lines)
    request_line = next(line for line in lines if line["event"] == "http.request")
    assert request_line["status"] == 201
    assert request_line["route"] == "/v1/users"
    assert request_line["organization_id"] == str(core_seed.orgs["a"])
    for secret in ("Awa", "Kouassi", subject, "example.invalid", core_seed.tokens[("a", "admin")]):
        assert secret not in output
