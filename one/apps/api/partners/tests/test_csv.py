"""Export CSV du portefeuille (CR-P3-01, CR-P3-02) : aucune formule de tableur exécutable.

Un nom de prestataire ou de catégorie est du texte saisi ailleurs : s'il commence par ``=``,
``+``, ``-``, ``@``, une tabulation ou un retour chariot (même précédé d'espaces), le tableur
l'exécuterait. Il est préfixé d'une apostrophe. Le test tombe si la garde est neutralisée.
Données fictives.
"""

from __future__ import annotations

import csv
import io
import uuid
from typing import Any

import pytest

from api.partners import service
from api.partners.schemas import InsurerPortfolio
from api.partners.service import portfolio_csv

DANGEROUS = ("=", "+", "-", "@", "\t", "\r", "\n", "\uff1d", "\uff0b", "\uff0d", "\uff20")
NAMES = [
    "=1+1",
    "+1",
    "-1",
    "@SUM(A1)",
    "\t=1",
    "\r=1",
    " =1",
    "\n=1",
    "  @x",
    "\uff1d1",
    "Clinique fictive",
]
SHOWN: dict[str, Any] = {"status": "disponible", "value": 1_000, "contributors": 5}


def _portfolio() -> InsurerPortfolio:
    return InsurerPortfolio.model_validate(
        {
            "period_from": "2026-09-28",
            "period_to": "2026-10-04",
            "generated_at": "2026-10-08T00:00:00Z",
            "k_anonymity_threshold": 5,
            "currency": "XOF",
            "members_total": SHOWN,
            "members_by_status": [],
            "premiums_xof": SHOWN,
            "claims_cost_xof": SHOWN,
            "loss_ratio_bp": SHOWN,
            "benefits_by_category": [{"category": "=x", "claims": SHOWN, "covered_xof": SHOWN}],
            "top_providers": [
                {"provider_id": str(uuid.uuid4()), "name": n, "claims": SHOWN, "covered_xof": SHOWN}
                for n in NAMES
            ],
            "other_providers": {"claims": SHOWN, "covered_xof": SHOWN},
            "decision_delay_mean_ms": SHOWN,
            "automation_rate_bp": SHOWN,
        }
    )


def _rows() -> list[list[str]]:
    return list(csv.reader(io.StringIO(portfolio_csv(_portfolio())), delimiter=";"))


def test_aucune_cellule_ne_commence_par_une_formule() -> None:
    rows = _rows()
    bad = [r for r in rows if any(c.lstrip(" ").startswith(DANGEROUS) for c in r[:2])]
    assert bad == []
    keys = [r[1] for r in rows if r[0] == "prestataire_dossiers"]
    assert keys[0] == "'=1+1"
    assert keys[-1] == "Clinique fictive"  # texte ordinaire inchangé


@pytest.mark.parametrize("name", NAMES[:-1])
def test_garde_de_formule(name: str) -> None:
    assert service.cell_text(name).startswith("'")


def test_mutation_garde_retiree_la_formule_passe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Témoin : sans la garde, « =1+1 » arrive tel quel dans le fichier."""
    monkeypatch.setattr(service, "cell_text", lambda value: value)
    keys = [r[1] for r in _rows() if r[0] == "prestataire_dossiers"]
    assert keys[0] == "=1+1"
