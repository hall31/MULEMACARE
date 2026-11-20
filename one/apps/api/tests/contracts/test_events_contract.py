"""Contrat L0 : ``specs/events.md`` décrit les six événements du PRD §6 en JSON Schema."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from api.tests.paths import EVENTS_MD, SCHEMA_SQL

EVENTS = (
    "claim.requested",
    "claim.decided",
    "contribution.received",
    "member.status_changed",
    "ledger.entry_posted",
    "authorization.synced",
)
# Aucune donnée identifiante ni médicale dans un événement : identifiants pseudonymes seulement.
FORBIDDEN_PROPERTY_FRAGMENTS = (
    "name",
    "nom",
    "phone",
    "telephone",
    "email",
    "birth",
    "naissance",
    "photo",
    "diagnos",
    "motif",
    "ordonnance",
    "prescription",
)

_JSON_BLOCK = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def _schemas() -> dict[str, dict[str, Any]]:
    text = EVENTS_MD.read_text(encoding="utf-8")
    out: dict[str, dict[str, Any]] = {}
    for block in _JSON_BLOCK.findall(text):
        doc = json.loads(block)
        title = doc.get("title")
        if isinstance(title, str):
            out[title] = doc
    return out


def _property_names(node: Any) -> list[str]:  # noqa: ANN401 — parcours d'un JSON arbitraire
    names: list[str] = []
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            names.extend(props)
        for value in node.values():
            names.extend(_property_names(value))
    elif isinstance(node, list):
        for value in node:
            names.extend(_property_names(value))
    return names


def test_six_evenements_documentes() -> None:
    assert set(EVENTS) <= set(_schemas()), sorted(set(EVENTS) - set(_schemas()))


@pytest.mark.parametrize("event", EVENTS)
def test_enveloppe_et_payload_stricts(event: str) -> None:
    schema = _schemas()[event]
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    for key in ("event_id", "event_type", "event_version", "occurred_at", "organization_id"):
        assert key in schema["required"], f"{event} : {key} requis"
    assert schema["properties"]["event_type"]["const"] == event
    payload = schema["properties"]["payload"]
    assert payload["type"] == "object"
    assert payload["additionalProperties"] is False
    assert payload["required"], f"{event} : payload sans champ requis"


@pytest.mark.parametrize("event", EVENTS)
def test_aucune_donnee_identifiante_ni_medicale(event: str) -> None:
    names = _property_names(_schemas()[event])
    bad = sorted({n for n in names for f in FORBIDDEN_PROPERTY_FRAGMENTS if f in n.lower()})
    assert not bad, f"{event} : propriétés interdites {bad}"


def test_types_d_evenements_alignes_sur_l_outbox() -> None:
    """La contrainte CHECK de outbox_events liste exactement les six événements."""
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    pattern = r"event_type\s+text\s+NOT NULL\s+CHECK \(event_type IN \((.*?)\)\)"
    match = re.search(pattern, sql, re.S)
    assert match, "contrainte event_type introuvable dans outbox_events"
    declared = set(re.findall(r"'([a-z_.]+)'", match.group(1)))
    assert declared == set(EVENTS)


def _conditions(event: str) -> list[dict[str, Any]]:
    payload = _schemas()[event]["properties"]["payload"]
    conditions = payload.get("allOf", [])
    assert isinstance(conditions, list)
    return conditions


def test_claim_decided_exige_la_regle_si_source_regle() -> None:
    expected = {
        "if": {"properties": {"source": {"const": "regle"}}, "required": ["source"]},
        "then": {"required": ["rule"], "properties": {"rule": {"type": "object"}}},
    }
    assert expected in _conditions("claim.decided")


def test_claim_decided_exige_l_auteur_si_source_humain() -> None:
    expected = {
        "if": {"properties": {"source": {"const": "humain"}}, "required": ["source"]},
        "then": {"required": ["decided_by"], "properties": {"decided_by": {"type": "string"}}},
    }
    assert expected in _conditions("claim.decided")


def test_authorization_synced_exige_un_motif_si_rejetee() -> None:
    expected = {
        "if": {"properties": {"outcome": {"const": "rejetee"}}, "required": ["outcome"]},
        "then": {"required": ["reason_code"], "properties": {"reason_code": {"type": "string"}}},
    }
    assert expected in _conditions("authorization.synced")
