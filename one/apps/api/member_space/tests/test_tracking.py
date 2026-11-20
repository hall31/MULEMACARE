"""Frise d'un remboursement : chaque statut de dossier donne quatre étapes, sans rien d'interne."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from api.member_space.tracking import STEP_KEYS, DecisionView, tracking_steps

REQUESTED = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
LATER = REQUESTED + timedelta(minutes=5)
R12 = DecisionView("accordee_auto", "R-12", 3, "R-12", LATER)
R20 = DecisionView("en_revue", "R-20", 2, "R-20", LATER)
HUMAN_OK = DecisionView("accordee", None, None, "MC-01", LATER + timedelta(hours=1))
HUMAN_NO = DecisionView("refusee", None, None, "MC-02", LATER + timedelta(hours=1))
DOCS = DecisionView("pieces_demandees", None, None, "MC-03", LATER + timedelta(hours=1))
CANCEL = DecisionView("annulee", None, None, "MC-04", LATER + timedelta(hours=1))


@pytest.mark.parametrize(
    ("status", "decisions", "states"),
    [
        ("demandee", [], ["fait", "en_cours", "a_venir", "a_venir"]),
        ("en_revue", [R20], ["fait", "en_cours", "a_venir", "a_venir"]),
        ("pieces_demandees", [R20, DOCS], ["fait", "en_cours", "a_venir", "a_venir"]),
        ("accordee_auto", [R12], ["fait", "fait", "en_cours", "a_venir"]),
        ("accordee", [R20, HUMAN_OK], ["fait", "fait", "en_cours", "a_venir"]),
        ("payee", [R12], ["fait", "fait", "fait", "fait"]),
        ("refusee", [R20, HUMAN_NO], ["fait", "refuse", "sans_objet", "sans_objet"]),
        ("annulee", [R12, CANCEL], ["fait", "annule", "sans_objet", "sans_objet"]),
    ],
)
def test_etats_des_quatre_etapes(
    status: str, decisions: list[DecisionView], states: list[str]
) -> None:
    steps = tracking_steps(status, REQUESTED, decisions)
    assert [s.key for s in steps] == list(STEP_KEYS)
    assert [s.state for s in steps] == states
    assert steps[0].at == REQUESTED


def test_accord_par_regle_porte_le_code_public_et_la_date() -> None:
    decision = tracking_steps("accordee_auto", REQUESTED, [R12])[1]
    assert (decision.rule_code, decision.rule_version, decision.reason_code) == ("R-12", 3, "R-12")
    assert decision.at == LATER


def test_accord_humain_apres_revue_porte_son_code_de_motif_sans_regle() -> None:
    decision = tracking_steps("accordee", REQUESTED, [R20, HUMAN_OK])[1]
    assert (decision.rule_code, decision.reason_code) == (None, "MC-01")
    assert decision.at == HUMAN_OK.decided_at


def test_revue_en_cours_montre_la_regle_de_routage() -> None:
    decision = tracking_steps("en_revue", REQUESTED, [R20])[1]
    assert (decision.state, decision.rule_code, decision.rule_version) == ("en_cours", "R-20", 2)


def test_pieces_demandees_montre_le_motif_administratif() -> None:
    decision = tracking_steps("pieces_demandees", REQUESTED, [R20, DOCS])[1]
    assert (decision.state, decision.reason_code) == ("en_cours", "MC-03")


def test_virement_et_reception_sans_date_tant_que_le_contrat_ne_la_porte_pas() -> None:
    """Aucune colonne ne date le virement (QUESTIONS Q-P1-03) : ``at`` reste nul."""
    steps = tracking_steps("payee", REQUESTED, [R12])
    assert (steps[2].at, steps[3].at) == (None, None)


def test_statut_inconnu_refuse() -> None:
    with pytest.raises(ValueError, match="statut"):
        tracking_steps("inconnu", REQUESTED, [])
