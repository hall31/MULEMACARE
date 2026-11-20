"""Contrat L0 : les seuils du PRD §5 vivent en données (règles versionnées), pas dans le code.

Les valeurs sont celles du prototype, marquées « à valider » (PRD §10 Q3, specs/QUESTIONS.md).
"""

from __future__ import annotations

from typing import Any

import psycopg
import pytest

EXPECTED_RULES: dict[str, tuple[int, dict[str, Any]]] = {
    "R-01": (1, {"statuts_ouvrant_droits": ["actif"], "suspension_apres_jours_impayes": 45}),
    "R-04": (2, {"convention_active_a_la_date_du_soin": True}),
    "R-07": (1, {"delai_source": "plan_version"}),
    "R-09": (1, {"perimetre": "famille"}),
    "R-12": (3, {"total_max_exclu_xof": 50000, "score_fraude_max_exclu": 0.2}),
    "R-20": (2, {"delai_cible_minutes": 120}),
    "ID-03": (1, {"codes_faux_avant_blocage": 3, "duree_blocage_minutes": 15}),
    "HL-01": (1, {"validite_accord_provisoire_minutes": 120}),
}


def _rules(dsn: str) -> dict[str, tuple[int, dict[str, Any], str]]:
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT r.code, v.version, v.params, v.state FROM rules r "
            "JOIN rule_versions v ON v.rule_id = r.id AND v.organization_id = r.organization_id "
            "WHERE v.state = 'en_vigueur'"
        ).fetchall()
    return {code: (version, params, state) for code, version, params, state in rows}


@pytest.mark.parametrize(("code", "expected"), list(EXPECTED_RULES.items()))
def test_seuils_du_prd_stockes_en_donnees(
    seeded_dsn: str, code: str, expected: tuple[int, dict[str, Any]]
) -> None:
    rules = _rules(seeded_dsn)
    assert code in rules, f"règle {code} absente du jeu de démonstration"
    version, params, _ = rules[code]
    assert (version, params) == expected


def test_carence_de_60_jours_portee_par_la_version_de_produit(seeded_dsn: str) -> None:
    with psycopg.connect(seeded_dsn) as conn:
        row = conn.execute(
            "SELECT waiting_period_days, coverage_rate_bp, family_annual_ceiling_xof "
            "FROM plan_versions WHERE state = 'en_vigueur'"
        ).fetchone()
    assert row == (60, 8000, 3_000_000)


def test_version_publiee_non_modifiable(seeded_dsn: str) -> None:
    """R3 : une version en vigueur ne change plus (sinon une décision n'est plus rejouable)."""
    with psycopg.connect(seeded_dsn) as conn, pytest.raises(psycopg.Error) as exc:
        conn.execute("UPDATE rule_versions SET params = '{}'::jsonb WHERE state = 'en_vigueur'")
    assert exc.value.sqlstate == "MCR01"


def test_versions_publiees_ne_se_chevauchent_pas(seeded_dsn: str) -> None:
    with psycopg.connect(seeded_dsn) as conn, pytest.raises(psycopg.Error) as exc:
        conn.execute(
            "INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, params, "
            "state) SELECT organization_id, rule_id, 99, DATE '2026-06-01', '{}'::jsonb, "
            "'en_vigueur' FROM rule_versions WHERE state = 'en_vigueur' LIMIT 1"
        )
    assert exc.value.sqlstate == "MCR02"


def test_version_de_regle_soumise_acceptee_et_figee(seeded_dsn: str) -> None:
    """Circuit brouillon → soumise → en vigueur, comme pour les versions de produit."""
    with psycopg.connect(seeded_dsn) as conn:
        # La version en vigueur est d'abord close (seul changement permis sur une version publiée).
        conn.execute(
            "UPDATE rule_versions SET valid_to = DATE '2026-12-31' WHERE state = 'en_vigueur' "
            "AND version = 3"
        )
        conn.execute(
            "INSERT INTO rule_versions (organization_id, rule_id, version, valid_from, params, "
            "state) SELECT organization_id, rule_id, 4, DATE '2027-01-01', "
            "'{\"total_max_exclu_xof\": 60000}'::jsonb, 'soumise' FROM rule_versions "
            "WHERE state = 'en_vigueur' AND version = 3"
        )
        with pytest.raises(psycopg.Error) as exc:
            conn.execute("UPDATE rule_versions SET params = '{}'::jsonb WHERE state = 'soumise'")
    assert exc.value.sqlstate == "MCR01"
