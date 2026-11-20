"""Connexion à la base de l'existant en LECTURE SEULE, prouvée de trois façons.

1. Le COMPTE : ``SHOW GRANTS FOR CURRENT_USER()`` ne doit accorder que SELECT, USAGE ou SHOW
   VIEW ; tout autre privilège, une option de délégation (GRANT OPTION) ou un rôle (dont les
   droits ne se lisent pas ici) refuse la connexion (IMP-04) avant toute lecture de données.
2. La SESSION : ``SET SESSION TRANSACTION READ ONLY`` puis ``START TRANSACTION READ ONLY``.
3. Chaque REQUÊTE : une seule instruction, qui commence par SELECT, sans commentaire, sans
   ``;``, sans mot qui écrit, verrouille, exporte ou attend (INTO, FOR UPDATE, SLEEP…), hors
   littéraux de chaîne (IMP-03). Seules trois instructions de session, constantes, passent
   hors de ce filtre.

Pilote : aucun n'est installé (dépendance à justifier, specs/DEPENDENCIES.md). ``connect_from_url``
charge PyMySQL s'il est présent, sinon refuse (IMP-07). La source est jointe sous la garde
d'egress (R9) : son hôte doit figurer dans ``infra/egress-allowlist.txt``.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Final, Protocol
from urllib.parse import unquote, urlsplit

from api.legacy_import.errors import ImportRefusedError

ALLOWED_PRIVILEGES: Final = frozenset({"SELECT", "USAGE", "SHOW VIEW"})
SHOW_GRANTS: Final = "SHOW GRANTS FOR CURRENT_USER()"
SESSION_READ_ONLY: Final = "SET SESSION TRANSACTION READ ONLY"
START_READ_ONLY: Final = "START TRANSACTION READ ONLY"
_SESSION_STATEMENTS: Final = frozenset({SHOW_GRANTS, SESSION_READ_ONLY, START_READ_ONLY})

_STRING_LITERAL: Final = re.compile(r"'(?:[^'\\]|'')*'")
_WRITES_OR_SIDE_EFFECTS: Final = re.compile(
    r"\b(INSERT|UPDATE|DELETE|REPLACE|MERGE|UPSERT|CREATE|ALTER|DROP|TRUNCATE|RENAME|GRANT"
    r"|REVOKE|CALL|DO|HANDLER|LOAD|LOCK|UNLOCK|SET|INTO|OUTFILE|DUMPFILE|SLEEP|BENCHMARK"
    r"|GET_LOCK|RELEASE_LOCK|LOAD_FILE|SHARE|EXECUTE|PREPARE|DEALLOCATE|KILL|SHUTDOWN"
    r"|FLUSH|RESET|PURGE|INSTALL|UNINSTALL|START|COMMIT|ROLLBACK|BEGIN)\b",
    re.IGNORECASE,
)
_GRANT_LINE: Final = re.compile(r"^GRANT\s+(?P<privs>.+?)\s+ON\s+", re.IGNORECASE)


def _refused_query() -> ImportRefusedError:
    return ImportRefusedError(
        "IMP-03", "Corrigez la requête du jeu de données : une seule instruction SELECT."
    )


def assert_select_only(statement: str) -> str:
    """Rend ``statement`` s'il ne peut que lire ; IMP-03 sinon (rien n'est envoyé)."""
    if "\\" in statement:
        raise _refused_query()
    # Hors littéraux de chaîne : ni guillemet restant, ni séparateur, ni commentaire.
    outside = _STRING_LITERAL.sub(" ", statement)
    if any(token in outside for token in ("'", '"', ";", "--", "/*", "*/", "#")):
        raise _refused_query()
    if not re.match(r"^\s*SELECT\s", outside, re.IGNORECASE):
        raise _refused_query()
    if _WRITES_OR_SIDE_EFFECTS.search(outside):
        raise _refused_query()
    return statement


def assert_read_only_grants(grants: Iterable[str]) -> None:
    """IMP-04 si le compte peut écrire, déléguer ou porte un rôle (droits non vérifiables)."""
    lines = [g.strip() for g in grants if g and g.strip()]
    if not lines:
        raise ImportRefusedError("IMP-04", "Aucun droit lisible : vérifiez le compte de lecture.")
    for line in lines:
        match = _GRANT_LINE.match(line)
        if match is None or re.search(r"WITH\s+(GRANT|ADMIN)\s+OPTION", line, re.IGNORECASE):
            raise ImportRefusedError(
                "IMP-04", "Utilisez un compte sans rôle ni délégation, limité à SELECT."
            )
        privileges = re.sub(r"\([^)]*\)", "", match["privs"])
        for privilege in privileges.split(","):
            if " ".join(privilege.split()).upper() not in ALLOWED_PRIVILEGES:
                raise ImportRefusedError(
                    "IMP-04", "Retirez au compte tout droit autre que SELECT (lecture seule)."
                )


class DbApiCursor(Protocol):
    """Curseur DB-API 2 (PEP 249), sous-ensemble utilisé."""

    @property
    def description(self) -> Sequence[Sequence[object]] | None: ...

    def execute(self, query: str) -> object: ...

    def fetchall(self) -> Sequence[Sequence[object]]: ...

    def close(self) -> None: ...


class DbApiConnection(Protocol):
    def cursor(self) -> DbApiCursor: ...

    def close(self) -> None: ...


class ReadOnlySource:
    """Connexion gardée : vérifie le compte et la session, puis n'exécute que des SELECT."""

    def __init__(self, connection: DbApiConnection) -> None:
        self._connection = connection
        self._verified = False

    def _run(self, statement: str) -> tuple[list[str], list[Sequence[object]]]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(statement)
            columns = [str(d[0]) for d in cursor.description or ()]
            return columns, list(cursor.fetchall()) if columns else []
        finally:
            cursor.close()

    def _session(self, statement: str) -> list[Sequence[object]]:
        if statement not in _SESSION_STATEMENTS:
            raise _refused_query()
        return self._run(statement)[1]

    def verify(self) -> None:
        """Compte limité à la lecture, puis session et transaction en lecture seule."""
        grants = [str(row[0]) for row in self._session(SHOW_GRANTS) if row]
        assert_read_only_grants(grants)
        self._session(SESSION_READ_ONLY)
        self._session(START_READ_ONLY)
        self._verified = True

    def select(self, statement: str) -> list[dict[str, object]]:
        if not self._verified:
            self.verify()
        columns, rows = self._run(assert_select_only(statement))
        return [dict(zip(columns, row, strict=True)) for row in rows]

    def close(self) -> None:
        self._connection.close()


def connect_from_url(url: str) -> ReadOnlySource:
    """``mysql://compte:secret@hôte:port/base`` → source gardée (PyMySQL requis, sinon IMP-07)."""
    parts = urlsplit(url)
    if parts.scheme != "mysql" or not parts.hostname or not parts.path.strip("/"):
        raise ImportRefusedError("IMP-08", "Format attendu : mysql://compte:secret@hôte:port/base")
    try:
        driver = importlib.import_module("pymysql")
    except ImportError:
        raise ImportRefusedError(
            "IMP-07", "Faites valider l'ajout de PyMySQL (MIT) ou fournissez un export CSV."
        ) from None
    options: Mapping[str, object] = {
        "host": parts.hostname,
        "port": parts.port or 3306,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": parts.path.strip("/"),
        "charset": "utf8mb4",
        "autocommit": False,
    }
    connection: DbApiConnection = driver.connect(**options)
    source = ReadOnlySource(connection)
    source.verify()
    return source
