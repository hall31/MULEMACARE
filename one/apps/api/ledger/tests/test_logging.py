"""Les journaux du grand livre passent par ``api.core.jsonlog`` (logger ``mulema``, JSON).

Événement nommé, champs pseudonymes, exception par son type et sa pile seulement.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator

import pytest

from api.core.jsonlog import LOGGER_NAME, JsonFormatter
from api.ledger.consumer import drain_outbox
from api.ledger.tests.support import (
    app_connection,
    contribution_received,
    run,
    setup_org,
    write_outbox,
)


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


def test_rejet_d_evenement_et_ecriture_en_json(insurance_dsn: str, captured: io.StringIO) -> None:
    org = setup_org(insurance_dsn, "journal-json")
    write_outbox(org, contribution_received(org, amount_xof=27500))
    rejected = contribution_received(org, channel="canal-inconnu")
    write_outbox(org, rejected)

    async def scenario() -> None:
        async with app_connection(insurance_dsn) as conn:
            report = await drain_outbox(conn, org.id)
        assert (report.posted, report.failed) == (1, 1)

    run(scenario())
    lines = _lines(captured)
    by_event = {str(line["event"]): line for line in lines}

    posted = by_event["ledger.entry_posted"]
    assert str(posted["logger"]).startswith(f"{LOGGER_NAME}.ledger")
    assert posted["organization_id"] == str(org.id)
    assert posted["source_type"] == "cotisation"

    failure = by_event["ledger.event_rejected"]
    assert str(failure["logger"]).startswith(f"{LOGGER_NAME}.ledger")
    assert failure["level"] == "error"
    assert failure["event_id"] == str(rejected.id)
    assert failure["code"] == "VAL-01"
    exception = failure["exception"]
    assert isinstance(exception, dict)
    assert exception["type"] == "LedgerError"
    # Le message d'erreur (qui peut citer une valeur saisie) n'est jamais journalisé.
    assert "canal-inconnu" not in json.dumps(lines)
