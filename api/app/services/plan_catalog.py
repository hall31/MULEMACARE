"""Catalogue plans déterministe (miroir config.php MulemaCare)."""

from __future__ import annotations

PLAN_CATALOG: dict[str, dict] = {
    "bronze": {
        "name": "Mulema Bronze",
        "ceiling_label": "500 000 FCFA / an / personne",
        "mcare_quota": 5,
        "prices": {
            "solo": {"EUR": 25, "USD": 28, "XAF": 15000},
            "couple": {"EUR": 45, "USD": 50, "XAF": 28000},
            "family": {"EUR": 75, "USD": 82, "XAF": 45000},
        },
    },
    "silver": {
        "name": "Mulema Silver",
        "ceiling_label": "1 500 000 FCFA / an / personne",
        "mcare_quota": 15,
        "prices": {
            "solo": {"EUR": 49, "USD": 55, "XAF": 30000},
            "couple": {"EUR": 89, "USD": 98, "XAF": 55000},
            "family": {"EUR": 139, "USD": 150, "XAF": 85000},
        },
    },
    "gold": {
        "name": "Mulema Gold",
        "ceiling_label": "3 500 000 FCFA / an / personne",
        "mcare_quota": 999,
        "prices": {
            "solo": {"EUR": 99, "USD": 110, "XAF": 65000},
            "couple": {"EUR": 189, "USD": 210, "XAF": 120000},
            "family": {"EUR": 280, "USD": 310, "XAF": 180000},
        },
    },
    "platinium": {
        "name": "Mulema Platinium",
        "ceiling_label": "8 000 000 FCFA / an / personne",
        "mcare_quota": 999,
        "prices": {
            "solo": {"EUR": 149, "USD": 165, "XAF": 95000},
            "couple": {"EUR": 279, "USD": 310, "XAF": 175000},
            "family": {"EUR": 399, "USD": 440, "XAF": 250000},
        },
    },
}

NETWORK_SAMPLE = [
    {"city": "Douala", "name": "Polyclinique Mermoz", "tiers_payant": True},
    {"city": "Yaoundé", "name": "Centre Médical Bastos", "tiers_payant": True},
    {"city": "Douala", "name": "Pharmacie des Nations", "tiers_payant": True},
]


def quote_amount(plan_id: str, composition: str, currency: str, cycle: str) -> float:
    plan = PLAN_CATALOG[plan_id]
    monthly = float(plan["prices"][composition][currency])
    if cycle == "monthly":
        return monthly
    return round(monthly * 12 * 0.90, 2)
