"""Logo de marque blanche : jamais exécutable, jamais servi depuis un hôte hors liste blanche.

Deux formes, rien d'autre (CR-P3-01) :

- ``url`` : chemin interne de l'instance (``/assets/…``, sans ``..`` ni ``//``), ou
  ``https://hôte[:port]/chemin`` dont l'hôte ET le port sont dans la liste DÉDIÉE des hôtes de
  logo de l'instance (``BrandingPorts.logo_hosts``, vide par défaut ; jamais la liste blanche
  d'egress, qui contient HealthOS et les bases — CR-P3-02) ; ni requête, ni fragment, ni
  identifiants ;
- ``data_uri`` : ``data:image/<png|webp|jpeg|svg+xml>;base64,…``, borné à ``MAX_LOGO_BYTES``
  décodés. Les images matricielles doivent porter la signature de leur type. Un SVG est
  « assaini par refus » : il doit déjà ne contenir que des éléments et attributs de la liste
  blanche ci-dessous (formes, dégradés, titre), aucune référence autre que locale (``url(#id)``),
  aucun script, gestionnaire ``on*``, ``style``, lien, image, ``use``, ``foreignObject``,
  DOCTYPE, entité, commentaire ni instruction de traitement. Seule la déclaration
  ``<?xml version="1.0" encoding="UTF-8"?>`` est admise, en tout premier (CR-P3-02). Les
  éléments actifs (``FORBIDDEN_ELEMENTS``) sont refusés NOMMÉMENT, avant la liste blanche et
  quel que soit leur espace de noms. Rien n'est réécrit : ce qui est stocké est exactement ce qui
  a été vérifié.
"""

from __future__ import annotations

import base64
import binascii
import re
import xml.etree.ElementTree as ET
from typing import Final
from urllib.parse import urlsplit

from api.integrations.egress import EgressAllowlist

MAX_LOGO_BYTES: Final = 32 * 1024
MAX_SRC_LENGTH: Final = 4 * ((MAX_LOGO_BYTES + 2) // 3) + 64
HTTPS_PORT: Final = 443
SVG_NS: Final = "http://www.w3.org/2000/svg"
MAX_SVG_ELEMENTS: Final = 2000
_FIRST_PRINTABLE: Final = 0x20
_DELETE: Final = 0x7F

_INTERNAL_PATH: Final = re.compile(r"^/[A-Za-z0-9._~/-]{1,512}$")
_URL_PATH: Final = re.compile(r"^(/[A-Za-z0-9._~/-]{0,512})?$")
_DATA_URI: Final = re.compile(
    r"^data:image/(?P<mime>png|webp|jpeg|svg\+xml);base64,(?P<data>[A-Za-z0-9+/]+={0,2})$"
)
_SIGNATURES: Final = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpeg": (b"\xff\xd8\xff",),
}
_XML_DECLARATION: Final = '<?xml version="1.0" encoding="UTF-8"?>'
_FORBIDDEN_MARKUP: Final = re.compile(r"<!|<\?|\]\]>", re.IGNORECASE)
_LOCAL_URL: Final = re.compile(r"url\(\s*#[A-Za-z][\w.-]*\s*\)")
_DANGEROUS_VALUE: Final = re.compile(
    r"url\(|javascript:|data:|expression\(|@import|<|>", re.IGNORECASE
)

ALLOWED_ELEMENTS: Final = frozenset(
    {
        "svg",
        "g",
        "path",
        "circle",
        "ellipse",
        "rect",
        "line",
        "polyline",
        "polygon",
        "title",
        "desc",
        "defs",
        "lineargradient",
        "radialgradient",
        "stop",
        "clippath",
    }
)
TEXT_ELEMENTS: Final = frozenset({"title", "desc"})
# Refusés nommément (en minuscules), même vides, même dans l'espace SVG : exécution, contenu
# étranger, ressource externe, animation (qui peut réécrire un attribut en ``javascript:``).
FORBIDDEN_ELEMENTS: Final = frozenset(
    {
        "foreignobject",
        "script",
        "style",
        "image",
        "use",
        "a",
        "iframe",
        "object",
        "embed",
        "feimage",
        "set",
        "animate",
        "animatemotion",
        "animatetransform",
        "handler",
        "listener",
        "discard",
    }
)
ALLOWED_ATTRIBUTES: Final = frozenset(
    {
        "id",
        "viewbox",
        "width",
        "height",
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "fx",
        "fy",
        "d",
        "points",
        "transform",
        "fill",
        "fill-opacity",
        "fill-rule",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "opacity",
        "clip-path",
        "clip-rule",
        "offset",
        "stop-color",
        "stop-opacity",
        "gradientunits",
        "gradienttransform",
        "clippathunits",
        "preserveaspectratio",
        "version",
        "role",
        "aria-label",
        "aria-hidden",
        "focusable",
    }
)


class LogoRejectedError(ValueError):
    """Logo refusé : ``field`` (``logo.kind`` ou ``logo.src``) et raison en français."""

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(reason)


def _refuse(reason: str) -> LogoRejectedError:
    return LogoRejectedError("logo.src", reason)


def _check_url(src: str, allowlist: EgressAllowlist) -> None:
    if src.startswith("/") and not src.startswith("//"):
        segments = src.split("/")[1:]
        if not _INTERNAL_PATH.fullmatch(src) or any(s in {"", ".", ".."} for s in segments):
            raise _refuse("Chemin interne invalide (ni « .. », ni « // », caractères simples).")
        return
    parts = urlsplit(src)
    if parts.scheme != "https" or not parts.netloc:
        raise _refuse("Adresse refusée : chemin interne ou https vers un hôte autorisé.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise _refuse("Adresse refusée : ni identifiants, ni paramètres, ni fragment.")
    try:
        port = parts.port or HTTPS_PORT
    except ValueError:
        raise _refuse("Port invalide.") from None
    host = parts.hostname or ""
    if not allowlist.allows(host, port):
        raise _refuse("Hôte hors de la liste blanche réseau de l'instance.")
    if not _URL_PATH.fullmatch(parts.path) or "/../" in f"{parts.path}/" or "//" in parts.path:
        raise _refuse("Chemin d'adresse invalide.")


def _local_name(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        namespace, _, local = tag[1:].partition("}")
        return namespace, local
    return None, tag


def _check_value(value: str) -> None:
    stripped = _LOCAL_URL.sub("", value)
    if _DANGEROUS_VALUE.search(stripped):
        raise _refuse("SVG refusé : référence externe ou contenu actif dans un attribut.")


def _parse_svg(document: str) -> ET.Element:
    body = document.removeprefix(_XML_DECLARATION)
    # DOCTYPE, entités, commentaires, CDATA, instructions de traitement : refusés AVANT l'analyse
    # (aucune expansion d'entité possible, aucune feuille de style liée).
    if _FORBIDDEN_MARKUP.search(body):
        raise _refuse("SVG refusé : DOCTYPE, entité, commentaire ou instruction interdits.")
    try:
        return ET.fromstring(body)  # noqa: S314 — DOCTYPE et entités exclus ci-dessus
    except ET.ParseError:
        raise _refuse("SVG illisible.") from None


def _check_svg(payload: bytes) -> None:
    try:
        document = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise _refuse("SVG refusé : encodage UTF-8 attendu.") from None
    root = _parse_svg(document)
    elements = list(root.iter())
    if len(elements) > MAX_SVG_ELEMENTS:
        raise _refuse("SVG trop complexe.")
    if _local_name(root.tag) != (SVG_NS, "svg"):
        raise _refuse("Document SVG attendu (élément racine svg).")
    for element in elements:
        namespace, local = _local_name(element.tag)
        if local.lower() in FORBIDDEN_ELEMENTS:
            raise _refuse(f"SVG refusé : élément « {local} » interdit.")
        if namespace != SVG_NS or local.lower() not in ALLOWED_ELEMENTS:
            raise _refuse(f"SVG refusé : élément « {local} » non admis.")
        has_text = bool((element.text or "").strip())
        if has_text and local.lower() not in TEXT_ELEMENTS:
            raise _refuse("SVG refusé : texte hors titre et description.")
        if (element.tail or "").strip():
            raise _refuse("SVG refusé : texte hors titre et description.")
        for name, value in element.attrib.items():
            attr_ns, attr = _local_name(name)
            if attr_ns is not None or attr.lower() not in ALLOWED_ATTRIBUTES:
                raise _refuse(f"SVG refusé : attribut « {attr} » non admis.")
            _check_value(value)


def _check_data_uri(src: str) -> None:
    match = _DATA_URI.fullmatch(src)
    if match is None:
        raise _refuse("data-URI refusé : image PNG, WebP, JPEG ou SVG en base64 seulement.")
    try:
        payload = base64.b64decode(match.group("data"), validate=True)
    except (binascii.Error, ValueError):
        raise _refuse("data-URI refusé : base64 invalide.") from None
    if len(payload) > MAX_LOGO_BYTES:
        raise _refuse(f"Logo trop lourd : {MAX_LOGO_BYTES // 1024} Ko au plus.")
    mime = match.group("mime")
    if mime == "svg+xml":
        _check_svg(payload)
    elif mime == "webp":
        if not (payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"):
            raise _refuse("Le contenu ne correspond pas au type d'image annoncé.")
    elif not payload.startswith(_SIGNATURES[mime]):
        raise _refuse("Le contenu ne correspond pas au type d'image annoncé.")


def validate_logo(kind: str, src: str, allowlist: EgressAllowlist) -> str:
    """Renvoie ``src`` tel quel s'il est sûr ; sinon lève ``LogoRejectedError``."""
    if kind not in {"url", "data_uri"}:
        raise LogoRejectedError("logo.kind", "Type de logo attendu : url ou data_uri.")
    if (
        not src
        or len(src) > MAX_SRC_LENGTH
        or any(ord(c) < _FIRST_PRINTABLE or ord(c) == _DELETE for c in src)
    ):
        raise _refuse("Logo vide, trop long ou avec des caractères de contrôle.")
    if kind == "url":
        _check_url(src, allowlist)
    else:
        _check_data_uri(src)
    return src
