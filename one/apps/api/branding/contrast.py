"""Contraste WCAG 2.2 : luminance relative et rapport, calcul unique du dépôt.

Partagé par la garde de marque blanche (``api.branding.palette``) et par le test des jetons du
contrat de design (``api/tests/contracts/test_design_tokens.py``) : le tableau §3 de
docs/POLISH_CONTRACT.md et le refus d'une couleur de marque reposent sur la même formule.
"""

from __future__ import annotations

import re
from typing import Final

HEX_COLOR: Final = re.compile(r"^#[0-9a-f]{6}$")
_LINEAR_THRESHOLD: Final = 0.04045


def relative_luminance(hex_color: str) -> float:
    """Luminance relative (WCAG 2.x) d'une couleur ``#rrggbb``."""
    value = hex_color.lower()
    if not HEX_COLOR.fullmatch(value):
        msg = f"couleur attendue au format #rrggbb : {hex_color!r}"
        raise ValueError(msg)
    channels = [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= _LINEAR_THRESHOLD else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(a: str, b: str) -> float:
    """Rapport de contraste entre deux couleurs (1 à 21), indépendant de l'ordre."""
    high, low = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)
