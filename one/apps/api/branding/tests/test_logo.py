"""Logo de marque blanche (CR-P3-01) : jamais exécutable, jamais hors liste blanche.

- URL : chemin interne de l'instance (``/…``) ou ``https://`` vers un hôte:port de la liste
  blanche d'egress ; rien d'autre (http, javascript:, data: déguisé, //hôte, identifiants).
- data-URI : PNG, WebP, JPEG (signature vérifiée) ou SVG assaini par liste blanche (éléments,
  attributs, références locales seulement) ; taille bornée ; tout le reste refusé.
Données fictives.
"""

from __future__ import annotations

import base64

import pytest

from api.branding import logo
from api.branding.logo import MAX_LOGO_BYTES, LogoRejectedError, validate_logo
from api.integrations.egress import EgressAllowlist, Endpoint

ALLOW = EgressAllowlist(frozenset({Endpoint("assets.ci.mulemacare.internal", 443)}))
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
SVG_OK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" role="img" '
    'aria-label="Logo fictif"><title>Logo</title><defs><linearGradient id="g">'
    '<stop offset="0" stop-color="#097268"/></linearGradient></defs>'
    '<circle cx="12" cy="12" r="10" fill="url(#g)"/><path d="M4 12h16" stroke="#064a43"/></svg>'
)


def _data(mime: str, payload: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(payload).decode()}"


def _svg(body: str) -> str:
    return _data("image/svg+xml", body.encode())


def _refused(kind: str, src: str) -> LogoRejectedError:
    with pytest.raises(LogoRejectedError) as caught:
        validate_logo(kind, src, ALLOW)
    return caught.value


# --- Acceptés -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "src"),
    [
        pytest.param("url", "/assets/logos/mutuelle-fictive.svg", id="chemin-interne"),
        pytest.param(
            "url", "https://assets.ci.mulemacare.internal/logos/fictif.png", id="hote-liste"
        ),
        pytest.param(
            "url", "https://assets.ci.mulemacare.internal:443/logos/fictif.png", id="port-explicite"
        ),
        pytest.param("data_uri", _data("image/png", PNG), id="png"),
        pytest.param("data_uri", _data("image/webp", WEBP), id="webp"),
        pytest.param("data_uri", _data("image/jpeg", JPEG), id="jpeg"),
        pytest.param("data_uri", _svg(SVG_OK), id="svg-assaini"),
        pytest.param(
            "data_uri", _svg('<?xml version="1.0" encoding="UTF-8"?>' + SVG_OK), id="svg-decl"
        ),
    ],
)
def test_logo_accepte(kind: str, src: str) -> None:
    assert validate_logo(kind, src, ALLOW) == src


# --- URL refusées ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        pytest.param("https://cdn.example.com/logo.png", id="hote-hors-liste"),
        pytest.param("https://assets.ci.mulemacare.internal:8443/l.png", id="port-hors-liste"),
        pytest.param("http://assets.ci.mulemacare.internal/l.png", id="http"),
        pytest.param("javascript:alert(1)", id="javascript"),
        pytest.param("data:image/png;base64,AAAA", id="data-en-url"),
        pytest.param("//cdn.example.com/logo.png", id="protocole-relatif"),
        pytest.param("/assets/../../etc/passwd", id="remontee"),
        pytest.param("/assets//cdn.example.com/x.png", id="double-barre"),
        pytest.param("https://user:pw@assets.ci.mulemacare.internal/l.png", id="identifiants"),
        pytest.param("https://assets.ci.mulemacare.internal/l.png?x=1", id="requete"),
        pytest.param("/assets/logo.png\nSet-Cookie: x", id="saut-de-ligne"),
        pytest.param("", id="vide"),
    ],
)
def test_url_refusee(src: str) -> None:
    assert _refused("url", src).field == "logo.src"


# --- data-URI refusés -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(SVG_OK.replace("<title>", "<script>alert(1)</script><title>"), id="script"),
        pytest.param(SVG_OK.replace('r="10"', 'r="10" onload="alert(1)"'), id="onload"),
        pytest.param(
            SVG_OK.replace("<title>", '<image href="https://cdn.example.com/x.png"/><title>'),
            id="image-externe",
        ),
        pytest.param(
            SVG_OK.replace("<title>", '<use href="https://cdn.example.com/s.svg#a"/><title>'),
            id="use-externe",
        ),
        pytest.param(
            SVG_OK.replace("<title>", '<a href="javascript:alert(1)"><path d="M0 0"/></a><title>'),
            id="lien-javascript",
        ),
        pytest.param(
            SVG_OK.replace("<title>", "<foreignObject><p>x</p></foreignObject><title>"),
            id="foreign-object",
        ),
        pytest.param(
            SVG_OK.replace("<title>", "<style>circle{fill:url(https://x)}</style><title>"),
            id="style",
        ),
        pytest.param(SVG_OK.replace('fill="url(#g)"', 'style="fill:red"'), id="attribut-style"),
        pytest.param(
            SVG_OK.replace('fill="url(#g)"', 'fill="url(https://cdn.example.com/p.svg#g)"'),
            id="url-externe-dans-attribut",
        ),
        pytest.param(
            '<!DOCTYPE svg [<!ENTITY x "y">]>' + SVG_OK.replace("Logo<", "&x;<"), id="entite"
        ),
        pytest.param(SVG_OK.replace("<title>", "<!-- c --><title>"), id="commentaire"),
        pytest.param(
            SVG_OK.replace("<title>", '<?xml-stylesheet href="x.css"?><title>'), id="instruction"
        ),
        pytest.param(
            SVG_OK.replace(
                'r="10"', 'r="10" xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://x"'
            ),
            id="xlink",
        ),
        pytest.param("<html><body>pas un svg</body></html>", id="pas-svg"),
        pytest.param("<svg", id="mal-forme"),
    ],
)
def test_svg_non_assaini_refuse(body: str) -> None:
    assert _refused("data_uri", _svg(body)).field == "logo.src"


@pytest.mark.parametrize(
    "src",
    [
        pytest.param(_data("text/html", b"<script>alert(1)</script>"), id="html"),
        pytest.param(_data("image/gif", b"GIF89a"), id="gif"),
        pytest.param(_data("image/png", b"<svg/>"), id="png-menteur"),
        pytest.param(_data("image/jpeg", PNG), id="jpeg-menteur"),
        pytest.param("data:image/png;base64,!!!", id="base64-invalide"),
        pytest.param("data:image/svg+xml," + SVG_OK, id="non-base64"),
        pytest.param("https://assets.ci.mulemacare.internal/l.png", id="url-en-data"),
        pytest.param(_data("image/png", PNG + b"\x00" * (MAX_LOGO_BYTES + 1)), id="trop-lourd"),
    ],
)
def test_data_uri_refuse(src: str) -> None:
    assert _refused("data_uri", src).field == "logo.src"


def test_type_de_logo_inconnu_refuse() -> None:
    assert _refused("css", "background:url(x)").field == "logo.kind"


# --- Revue P3 (CR-P3-02) : instruction de traitement, foreignObject -----------------------------


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(
            '<?xml-stylesheet type="text/css" href="https://cdn.example.com/x.css"?>' + SVG_OK,
            id="feuille-de-style-en-tete",
        ),
        pytest.param(
            '<?xml version="1.0"?><?xml-stylesheet href="https://cdn.example.com/x.css"?>' + SVG_OK,
            id="feuille-de-style-apres-declaration",
        ),
        pytest.param("<?xml-foo?>" + SVG_OK, id="instruction-inconnue"),
        pytest.param('<?xml version="1.0"?>' + SVG_OK, id="declaration-sans-encodage"),
        pytest.param('<?xml version="1.1" encoding="UTF-8"?>' + SVG_OK, id="version-1-1"),
        pytest.param('<?xml version="1.0" encoding="ISO-8859-1"?>' + SVG_OK, id="autre-encodage"),
        pytest.param(
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>' + SVG_OK, id="standalone"
        ),
        pytest.param(' <?xml version="1.0" encoding="UTF-8"?>' + SVG_OK, id="blanc-en-tete"),
    ],
)
def test_seule_la_declaration_xml_stricte_est_admise(body: str) -> None:
    """``<?xml version="1.0" encoding="UTF-8"?>`` en tête, rien d'autre : toute autre
    instruction de traitement (feuille de style liée…) est refusée."""
    assert _refused("data_uri", _svg(body)).field == "logo.src"


@pytest.mark.parametrize(
    "element",
    ["foreignObject", "script", "style", "image", "use", "a", "set", "animate", "iframe"],
)
def test_element_actif_refuse_explicitement(element: str) -> None:
    """Refus nommé (pas seulement « hors liste ») : même vide, même dans l'espace SVG."""
    body = SVG_OK.replace("<title>", f"<{element}/><title>")
    reason = _refused("data_uri", _svg(body)).reason
    assert "interdit" in reason, reason


def test_elements_interdits_jamais_dans_la_liste_blanche() -> None:
    assert logo.ALLOWED_ELEMENTS.isdisjoint(logo.FORBIDDEN_ELEMENTS)
    assert "foreignobject" in logo.FORBIDDEN_ELEMENTS
