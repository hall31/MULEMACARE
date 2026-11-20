"""Plan de comptes initial (LOTS.md, L3) et schémas d'écriture des événements consommés.

Les libellés et classes reprennent ``specs/seeds/demo.sql``. Les affectations ci-dessous sont
les seules que les contrats fixent (specs/events.md : accord → 6011 / 4011, cotisation →
512x / 7061) ; aucun compte n'est deviné pour un canal absent du plan (Q-L0-11).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from api.ledger.domain import AccountClass


@dataclass(frozen=True, slots=True)
class Account:
    code: str
    label: str
    account_class: AccountClass


CHART_OF_ACCOUNTS: Final[tuple[Account, ...]] = (
    Account("4011", "Prestataires à payer", "passif"),
    Account("5110", "Banque", "actif"),
    Account("5121", "Mobile money · Wave", "actif"),
    Account("5122", "Mobile money · Orange Money", "actif"),
    Account("6011", "Prestations santé", "charge"),
    Account("7061", "Cotisations acquises", "produit"),
)

# Prise en charge accordée : charge de prestations contre dette envers le prestataire.
CLAIM_EXPENSE: Final = "6011"
PROVIDER_PAYABLE: Final = "4011"

# Cotisation reçue : trésorerie du canal contre produit de cotisations.
CONTRIBUTION_REVENUE: Final = "7061"
CASH_ACCOUNT_BY_CHANNEL: Final[dict[str, str]] = {
    "wave": "5121",
    "orange_money": "5122",
    "virement": "5110",
    "prelevement_employeur": "5110",
    # "mtn_momo" : pas de compte dans le plan initial (Q-L0-11).
    # "simulation" : canal de développement, compte non décidé.
}
