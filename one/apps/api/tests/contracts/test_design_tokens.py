"""Contrat L0 : jetons du thème MulemaCare One (clair, sombre, plein soleil), rien d'autre.

Les valeurs attendues suivent la direction « Registre émeraude » (Bio-Clinical Emerald du site
preprod.mulemacare.com) fixée par docs/POLISH_CONTRACT.md le 2026-10-01. Elles remplacent
l'accent indigo du prototype : l'ancien échantillon (#2e3fa6…) décrivait un thème abandonné.
Le tableau de contraste du contrat (§3) est recalculé ici avec le calcul partagé
``api.branding.contrast`` (le même que la garde de marque blanche, CR-P3-01) : un jeton qui
fait tomber une paire sous WCAG AA (4,5:1 texte, 3:1 composant) ou sous 7:1 en plein soleil
casse ce test.
"""

from __future__ import annotations

import re

import pytest

from api.branding.contrast import contrast_ratio
from api.tests.paths import TOKENS_CSS

COLOR_TOKENS = (
    "--bg", "--surface", "--sunk", "--line", "--line-2",
    "--fg", "--fg-2", "--fg-3",
    "--accent", "--accent-2", "--accent-fg",
    "--ok", "--ok-bg", "--warn", "--warn-bg", "--crit", "--crit-bg",
    "--info", "--info-bg",
)  # fmt: skip

# Direction « Registre émeraude » (docs/POLISH_CONTRACT.md §2).
LIGHT_SAMPLES = {
    "--bg": "#f6f9fb",
    "--fg": "#0f172a",
    "--accent": "#097268",
    "--ok": "#166534",
    "--crit": "#b91c1c",
}
DARK_SAMPLES = {"--bg": "#0d1417", "--accent": "#4fc2b0", "--ok": "#6fcf8e", "--crit": "#f38e86"}
SUN_SAMPLES = {"--bg": "#ffffff", "--fg": "#000000", "--accent": "#00473f", "--crit": "#8e0000"}

# Paires texte/fond (contrat §3). Le plein soleil exige 7:1 (WCAG AAA) sur chacune.
TEXT_PAIRS = (
    ("--fg", "--bg"), ("--fg", "--surface"), ("--fg", "--sunk"), ("--fg", "--accent-2"),
    ("--fg-2", "--bg"), ("--fg-2", "--surface"), ("--fg-2", "--sunk"),
    ("--fg-3", "--bg"), ("--fg-3", "--surface"), ("--fg-3", "--sunk"),
    ("--accent", "--bg"), ("--accent", "--surface"), ("--accent", "--accent-2"),
    ("--accent-fg", "--accent"), ("--accent-fg", "--accent-hover"),
    ("--ok", "--ok-bg"), ("--ok", "--surface"),
    ("--warn", "--warn-bg"), ("--warn", "--surface"),
    ("--crit", "--crit-bg"), ("--crit", "--surface"),
    ("--info", "--info-bg"), ("--info", "--surface"),
    ("--brand-on-deep", "--brand-deep"), ("--brand-on-deep-2", "--brand-deep"),
)  # fmt: skip
# Composants et repères graphiques (WCAG 1.4.11) : bord de champ, anneau de focus.
UI_PAIRS = (
    ("--line-2", "--surface"),
    ("--line-2", "--bg"),
    ("--focus", "--surface"),
    ("--focus", "--bg"),
)


def _css() -> str:
    return TOKENS_CSS.read_text(encoding="utf-8")


def _block(selector_pattern: str) -> dict[str, str]:
    match = re.search(selector_pattern + r"\s*\{(.*?)\}", _css(), re.DOTALL)
    assert match, f"bloc introuvable : {selector_pattern}"
    return {
        k: v.strip().lower()
        for k, v in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", match.group(1))
    }


LIGHT = r"(?m)^:root"
DARK = r':root\[data-theme="dark"\]'
SUN = r"\[data-sun\]"


def _theme(selector: str) -> dict[str, str]:
    """Jetons effectifs : le bloc clair, surchargé par le bloc du thème."""
    tokens = _block(LIGHT)
    if selector != LIGHT:
        tokens.update(_block(selector))
    return tokens


@pytest.mark.parametrize(
    ("selector", "samples"),
    [
        pytest.param(LIGHT, LIGHT_SAMPLES, id="clair"),
        pytest.param(DARK, DARK_SAMPLES, id="sombre"),
        pytest.param(SUN, SUN_SAMPLES, id="plein-soleil"),
    ],
)
def test_bloc_complet_et_fidele_a_la_direction(selector: str, samples: dict[str, str]) -> None:
    tokens = _block(selector)
    missing = [t for t in COLOR_TOKENS if t not in tokens]
    assert not missing, f"jetons manquants : {missing}"
    for name, value in samples.items():
        assert tokens[name] == value


@pytest.mark.parametrize(
    ("selector", "text_min"),
    [
        pytest.param(LIGHT, 4.5, id="clair"),
        pytest.param(DARK, 4.5, id="sombre"),
        pytest.param(SUN, 7.0, id="plein-soleil"),
    ],
)
def test_contrastes_du_contrat(selector: str, text_min: float) -> None:
    tokens = _theme(selector)
    failures = [
        f"{fg} sur {bg} : {contrast_ratio(tokens[fg], tokens[bg]):.2f} < {minimum}"
        for pairs, minimum in ((TEXT_PAIRS, text_min), (UI_PAIRS, 3.0))
        for fg, bg in pairs
        if contrast_ratio(tokens[fg], tokens[bg]) < minimum
    ]
    assert not failures, failures


def test_l_or_reste_decoratif_sur_fond_clair() -> None:
    """L'or de marque échoue AA en texte sur fond clair : le contrat l'interdit en texte (§3)."""
    tokens = _theme(LIGHT)
    assert contrast_ratio(tokens["--brand-gold"], tokens["--surface"]) < 4.5
    assert contrast_ratio(tokens["--brand-gold"], tokens["--surface"]) >= 3.0, (
        "repère graphique : 3:1 minimum"
    )


def test_l_accent_n_est_pas_un_statut() -> None:
    for selector in (LIGHT, DARK, SUN):
        tokens = _theme(selector)
        assert tokens["--accent"] not in {
            tokens["--ok"],
            tokens["--warn"],
            tokens["--crit"],
            tokens["--info"],
        }


def test_sombre_suit_aussi_le_systeme() -> None:
    assert "prefers-color-scheme: dark" in _css()


def test_sombre_systeme_identique_au_sombre_force() -> None:
    """Les deux blocs sombres sont dupliqués (CSS pur) : ils ne doivent pas diverger."""
    system = _block(r'prefers-color-scheme: dark\)\s*\{\s*:root:not\(\[data-theme="light"\]\)')
    assert system == _block(DARK)


def test_mouvement_reduit_annule_les_deplacements() -> None:
    css = _css()
    assert "prefers-reduced-motion: reduce" in css
    reduced = _block(r"prefers-reduced-motion: reduce\)\s*\{\s*:root")
    assert reduced["--move-sm"] == "0px"
    assert reduced["--move-md"] == "0px"


def test_aucun_autre_theme() -> None:
    assert "data-skin" not in _css(), "les thèmes alternatifs du prototype sont exclus"
