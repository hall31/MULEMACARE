"""Garde de contraste de la marque blanche (CR-P3-01) : calcul partagé, liste fermée, paires.

1. Le calcul est celui du contrat de design : mêmes valeurs que le tableau §3 de
   docs/POLISH_CONTRACT.md, et ``test_design_tokens.py`` s'en sert (une seule méthode).
2. La palette de base du serveur est identique aux jetons de ``specs/design`` (anti-dérive).
3. Les paires gardées sont exactement celles du contrat qui touchent un jeton surchargeable.
4. Garde : une couleur qui fait tomber une paire sous AA (clair ou sombre) est refusée, avec la
   paire, le thème et le rapport ; une couleur d'un statut est refusée ; toute clé hors liste
   fermée, tout thème hors clair/sombre, toute valeur qui n'est pas ``#RRGGBB`` est refusée.
5. Mutation : seuil neutralisé, la même couleur passe (le test ci-dessus est donc porteur).
"""

from __future__ import annotations

import pytest

from api.branding import palette
from api.branding.contrast import contrast_ratio
from api.branding.palette import (
    BASE_TOKENS,
    GUARDED_TEXT_PAIRS,
    GUARDED_UI_PAIRS,
    OVERRIDABLE_TOKENS,
    PaletteProblem,
    check_theme_overrides,
    effective_tokens,
)
from api.tests.contracts import test_design_tokens as design

GOLD = "#d97706"  # or de marque : 3,19:1 sur blanc, échoue AA (POLISH_CONTRACT §3)
ROYAL_700 = "#1d4ed8"  # bleu marque fictive, AA en clair
ROYAL_900 = "#1e3a8a"


def _fields(problems: list[PaletteProblem]) -> set[str]:
    return {p.field for p in problems}


# --- 1. Calcul partagé ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fg", "bg", "expected"),
    [
        ("#0f172a", "#f6f9fb", 16.88),  # --fg / --bg clair
        ("#097268", "#ffffff", 5.80),  # --accent / --surface clair
        ("#d97706", "#ffffff", 3.19),  # or : décor seul
        ("#4fc2b0", "#131c20", 7.97),  # --accent / --surface sombre
    ],
)
def test_calcul_identique_au_tableau_du_contrat(fg: str, bg: str, expected: float) -> None:
    assert round(contrast_ratio(fg, bg), 2) == expected


def test_le_test_des_jetons_utilise_le_meme_calcul() -> None:
    assert vars(design)["contrast_ratio"] is contrast_ratio


# --- 2. Palette de base = jetons du contrat de design ---------------------------------------------


@pytest.mark.parametrize(("theme", "selector"), [("light", design.LIGHT), ("dark", design.DARK)])
def test_palette_de_base_identique_aux_jetons_css(theme: str, selector: str) -> None:
    css = design._theme(selector)
    for token, value in BASE_TOKENS[theme].items():
        assert css[token] == value, f"{theme} {token} : serveur {value}, contrat {css[token]}"


def test_la_palette_de_base_passe_la_garde() -> None:
    assert check_theme_overrides({}) == []
    assert check_theme_overrides({"light": {}, "dark": {}}) == []


# --- 3. Paires gardées --------------------------------------------------------------------------


def test_paires_gardees_issues_du_contrat() -> None:
    css_names = {f"--{t.replace('_', '-')}" for t in OVERRIDABLE_TOKENS} | {"--focus"}
    expected_text = {p for p in design.TEXT_PAIRS if set(p) & css_names}
    expected_ui = {p for p in design.UI_PAIRS if set(p) & css_names}
    assert set(GUARDED_TEXT_PAIRS) == expected_text
    assert set(GUARDED_UI_PAIRS) == expected_ui


def test_liste_fermee_des_jetons_surchargeables() -> None:
    assert OVERRIDABLE_TOKENS == ("accent", "accent_hover", "accent_fg", "brand_deep")


def test_le_focus_suit_l_accent() -> None:
    tokens = effective_tokens("light", {"accent": ROYAL_700})
    assert tokens["--focus"] == ROYAL_700


# --- 4. Garde -------------------------------------------------------------------------------------


def test_marque_conforme_acceptee() -> None:
    assert check_theme_overrides({"light": {"accent": ROYAL_700, "accent_hover": ROYAL_900}}) == []


def test_accent_or_refuse_en_clair_avec_paires_et_rapports() -> None:
    problems = check_theme_overrides({"light": {"accent": GOLD}})
    assert "theme.light.accent" in _fields(problems)
    texts = " ".join(p.message for p in problems)
    assert "--surface" in texts
    assert "3,19" in texts
    assert "4,5" in texts


def test_texte_sur_accent_illisible_refuse_en_sombre() -> None:
    """Accent sombre éclairci, texte sur accent laissé foncé : la paire bouton tombe."""
    problems = check_theme_overrides({"dark": {"accent_fg": "#4fc2b0"}})
    assert "theme.dark.accent_fg" in _fields(problems)


def test_emeraude_profond_trop_clair_refuse() -> None:
    problems = check_theme_overrides({"light": {"brand_deep": "#9be4dc"}})
    assert "theme.light.brand_deep" in _fields(problems)


def test_accent_egal_a_un_statut_refuse() -> None:
    """L'accent ne marque jamais un statut (POLISH_CONTRACT §5)."""
    problems = check_theme_overrides({"light": {"accent": "#166534"}})  # = --ok
    assert any("statut" in p.message for p in problems)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        pytest.param({"light": {"bg": "#000000"}}, "theme.light.bg", id="fond-non-surchargeable"),
        pytest.param({"light": {"--accent": "#1d4ed8"}}, "theme.light.--accent", id="nom-css"),
        pytest.param({"sun": {"accent": "#1d4ed8"}}, "theme.sun", id="plein-soleil-intouchable"),
        pytest.param(
            {"light": {"accent": "red; background:url(x)"}},
            "theme.light.accent",
            id="css-libre",
        ),
        pytest.param({"light": {"accent": "#1d4ed"}}, "theme.light.accent", id="hex-court"),
        pytest.param({"light": {"accent": "rgb(0,0,0)"}}, "theme.light.accent", id="rgb"),
        pytest.param({"light": "#1d4ed8"}, "theme.light", id="theme-non-objet"),
    ],
)
def test_hors_liste_fermee_refuse(overrides: dict[str, object], field: str) -> None:
    problems = check_theme_overrides(overrides)
    assert field in _fields(problems)
    assert all(p.kind == "jeton" for p in problems if p.field == field)


def test_contraste_et_liste_fermee_distingues() -> None:
    contrast = check_theme_overrides({"light": {"accent": GOLD}})
    closed = check_theme_overrides({"light": {"bg": "#000000"}})
    assert {p.kind for p in contrast} == {"contraste"}
    assert {p.kind for p in closed} == {"jeton"}


# --- 5. Mutation : seuil neutralisé ---------------------------------------------------------


def test_mutation_seuil_neutralise_la_couleur_passe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Témoin : sans le seuil AA, l'or passerait ; c'est donc la garde qui le refuse."""
    monkeypatch.setattr(palette, "TEXT_MINIMUM", 1.0)
    monkeypatch.setattr(palette, "UI_MINIMUM", 1.0)
    assert check_theme_overrides({"light": {"accent": GOLD, "accent_hover": "#b45309"}}) == []
