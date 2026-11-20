"""Extraction de la source en mémoire, en lecture seule : export CSV, dump SQL ou MySQL gardé.

Le résultat (``SourceSnapshot``) n'est jamais écrit sur disque ni journalisé : il ne vit que le
temps de la commande. Volume visé : quelques milliers de lignes (≈ 420 adhérents documentés).

- CSV : un fichier ``<jeu>.csv`` (UTF-8, en-tête) par jeu de données de la correspondance ;
  une cellule vide vaut NULL (le CSV ne distingue pas les deux).
- Dump SQL (mysqldump) : instructions ``INSERT INTO `table` … VALUES (…)`` de la table du même
  nom que le jeu ; les colonnes viennent de la liste de l'INSERT ou du ``CREATE TABLE`` du dump.
  Un jeu composé (jointure, alias) exige un export CSV : ses colonnes manquent → IMP-08.
- MySQL : ``readonly.ReadOnlySource`` (compte, session et requêtes en lecture seule).
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from api.legacy_import.errors import ImportRefusedError
from api.legacy_import.readonly import ReadOnlySource
from api.legacy_import.spec import ImportSpec

type SourceRow = Mapping[str, object]

NULL: Final = object()


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    """Lignes de chaque jeu de données ; ``origin`` : csv, dump ou mysql."""

    origin: str
    datasets: Mapping[str, tuple[SourceRow, ...]]

    def rows(self, dataset: str) -> tuple[SourceRow, ...]:
        return self.datasets.get(dataset, ())


def _required_columns(spec: ImportSpec) -> dict[str, set[str]]:
    needed: dict[str, set[str]] = {}
    for entity in spec.entities.values():
        needed.setdefault(entity.dataset.name, set()).update(entity.columns())
    return needed


def _check_columns(dataset: str, present: set[str], needed: set[str]) -> None:
    if missing := needed - present:
        raise ImportRefusedError(
            "IMP-08",
            f"Jeu « {dataset} » : colonne(s) absente(s) {sorted(missing)} ; "
            "fournissez un export CSV avec les colonnes de la correspondance.",
        )


def read_csv_export(directory: Path, spec: ImportSpec) -> SourceSnapshot:
    datasets: dict[str, tuple[SourceRow, ...]] = {}
    for name, needed in _required_columns(spec).items():
        path = directory / f"{name}.csv"
        if not path.is_file():
            raise ImportRefusedError("IMP-08", f"Fichier attendu : {name}.csv")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            _check_columns(name, set(reader.fieldnames or ()), needed)
            datasets[name] = tuple(
                {k: (v if v != "" else None) for k, v in row.items() if k in needed}
                for row in reader
            )
    return SourceSnapshot("csv", datasets)


# --- dump SQL ---------------------------------------------------------------------------------

_ESCAPES: Final = {"0": "\0", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a", "b": "\b"}


def _string_end(text: str, start: int) -> int:
    """Index du guillemet fermant la chaîne ouverte en ``start`` (``\\x`` et ``''`` gérés)."""
    quote, i, size = text[start], start + 1, len(text)
    while i < size:
        if text[i] == "\\":
            i += 2
        elif text[i] == quote and i + 1 < size and text[i + 1] == quote:
            i += 2
        elif text[i] == quote:
            return i
        else:
            i += 1
    return size - 1


def _statements(text: str) -> Iterator[str]:
    """Instructions séparées par ``;`` hors chaînes et commentaires (commentaires retirés)."""
    buffer: list[str] = []
    i, size = 0, len(text)
    while i < size:
        char = text[i]
        if char in "'\"`":
            end = _string_end(text, i)
            buffer.append(text[i : end + 1])
            i = end + 1
        elif text.startswith("--", i) or char == "#":
            newline = text.find("\n", i)
            i = size if newline < 0 else newline
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2)
            i = size if close < 0 else close + 2
        elif char == ";":
            yield "".join(buffer).strip()
            buffer = []
            i += 1
        else:
            buffer.append(char)
            i += 1
    if tail := "".join(buffer).strip():
        yield tail


def _literal(token: str) -> object:
    if token.upper() == "NULL":
        return None
    if token.startswith("'"):
        body, out, i = token[1:-1], [], 0
        while i < len(body):
            if body[i] == "\\" and i + 1 < len(body):
                out.append(_ESCAPES.get(body[i + 1], body[i + 1]))
                i += 2
            elif body.startswith("''", i):
                out.append("'")
                i += 2
            else:
                out.append(body[i])
                i += 1
        return "".join(out)
    return token  # nombre : gardé en texte, normalisé ensuite (jamais en flottant)


def _tuples(values: str) -> Iterator[list[object]]:
    """``(1,'a'),(2,NULL)`` → [[1, 'a'], [2, None]]."""
    i, size = 0, len(values)
    while i < size:
        if values[i] != "(":
            i += 1
            continue
        row: list[object] = []
        i += 1
        token: list[str] = []
        while i < size and values[i] != ")":
            char = values[i]
            if char == "'":
                end = _string_end(values, i)
                token.append(values[i : end + 1])
                i = end + 1
            elif char == ",":
                row.append(_literal("".join(token).strip()))
                token = []
                i += 1
            else:
                token.append(char)
                i += 1
        row.append(_literal("".join(token).strip()))
        yield row
        i += 1


_CREATE: Final = re.compile(r"^CREATE TABLE (?:IF NOT EXISTS )?`?(\w+)`?\s*\((.*)\)", re.S | re.I)
_INSERT: Final = re.compile(
    r"^INSERT INTO `?(\w+)`?\s*(?:\(([^)]*)\))?\s*VALUES\s*(.*)$", re.S | re.I
)


def read_sql_dump(path: Path, spec: ImportSpec) -> SourceSnapshot:
    if not path.is_file():
        raise ImportRefusedError("IMP-08", "Fichier de dump introuvable.")
    needed = _required_columns(spec)
    columns: dict[str, list[str]] = {}
    rows: dict[str, list[SourceRow]] = {name: [] for name in needed}
    for statement in _statements(path.read_text(encoding="utf-8")):
        if created := _CREATE.match(statement):
            columns[created[1]] = [
                m[1] for m in re.finditer(r"^\s*`(\w+)`", created[2], flags=re.MULTILINE)
            ]
        elif (inserted := _INSERT.match(statement)) and inserted[1] in needed:
            table = inserted[1]
            names = (
                [c.strip(" `") for c in inserted[2].split(",")]
                if inserted[2]
                else columns.get(table, [])
            )
            columns.setdefault(table, names)
            for values in _tuples(inserted[3]):
                if len(values) != len(names):
                    raise ImportRefusedError("IMP-08", f"Table « {table} » : ligne mal formée.")
                rows[table].append(
                    {n: v for n, v in zip(names, values, strict=True) if n in needed[table]}
                )
    for name, wanted in needed.items():
        _check_columns(name, set(columns.get(name, [])), wanted)
    return SourceSnapshot("dump", {name: tuple(found) for name, found in rows.items()})


def read_mysql(source: ReadOnlySource, spec: ImportSpec) -> SourceSnapshot:
    datasets: dict[str, tuple[SourceRow, ...]] = {}
    selects = {e.dataset.name: e.dataset.select for e in spec.entities.values()}
    for name, needed in _required_columns(spec).items():
        found = source.select(selects[name])
        if found:
            _check_columns(name, set(found[0]), needed)
        datasets[name] = tuple({k: v for k, v in row.items() if k in needed} for row in found)
    return SourceSnapshot("mysql", datasets)
