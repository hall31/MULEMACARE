"""Transformation PURE : instantané de la source + correspondance → lignes prêtes pour One.

Aucune E/S. Chaque ligne de la source finit dans exactement une catégorie :
- ``records`` : prête à écrire (avec ses clés d'origine et ses références) ;
- ``rejections`` : écartée avec un motif REJ-xx et le champ en cause (jamais la valeur) ;
- ``exclusions`` : hors périmètre par la table de correspondance (EXC-xx) ;
- ``filtered`` : écartée par le filtre déclaré de la correspondance (``only_when``).
Une ligne qui en référence une autre rejetée est rejetée à son tour (REJ-04) : rien d'orphelin.

Les références se résolvent DANS l'instantané (une source se lit toujours en entier) ; l'écriture
les traduit ensuite en identifiants de One par ``external_ids``.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Final

from api.legacy_import import normalize as n
from api.legacy_import.errors import RowRejectedError
from api.legacy_import.sources import SourceRow, SourceSnapshot
from api.legacy_import.spec import LOAD_ORDER, EntitySpec, ImportSpec, Kind
from api.legacy_import.statuses import (
    IMPORTED_MEMBER_STATUS,
    STATUS_MAP,
    STATUS_MAP_VERSION,
    Excluded,
    lookup,
)

PLAN_CODE: Final = re.compile(r"^[A-Z0-9-]{2,32}$")
_MAX_ROWS_PER_DEPENDENT_LIST: Final = 30


@dataclass(frozen=True, slots=True)
class PersonData:
    given_name: str
    family_name: str
    birth_date: date
    phone_e164: str | None


@dataclass(frozen=True, slots=True)
class Record:
    """Ligne prête pour One. ``keys`` : clés d'origine ``nom:valeur`` (la première identifie la
    ligne dans les rapports). ``refs`` : rôle → (type, clé d'origine de la cible)."""

    kind: Kind
    keys: tuple[tuple[str, str], ...]
    values: Mapping[str, object]
    refs: Mapping[str, tuple[Kind, str]] = field(default_factory=dict)
    person_keys: tuple[tuple[str, str], ...] = ()
    import_status: str | None = None

    @property
    def primary(self) -> str:
        return self.keys[0][1]


@dataclass(frozen=True, slots=True)
class Rejection:
    dataset: str
    row: str  # clé d'origine (ou n° de ligne si la clé est illisible)
    code: str
    field: str


@dataclass(frozen=True, slots=True)
class Exclusion:
    dataset: str
    row: str
    code: str


@dataclass
class Staged:
    records: dict[Kind, list[Record]] = field(default_factory=lambda: defaultdict(list))
    rejections: list[Rejection] = field(default_factory=list)
    exclusions: list[Exclusion] = field(default_factory=list)
    filtered: Counter[str] = field(default_factory=Counter)
    warnings: list[Rejection] = field(default_factory=list)
    # Adhésions à l'adresse électronique identique (normalisée) : doublons PROBABLES, à revoir.
    # Seules les clés d'origine figurent ici ; l'adresse ne sort jamais de la mémoire.
    probable_duplicates: list[tuple[str, ...]] = field(default_factory=list)
    status_map_version: str = STATUS_MAP_VERSION

    def by_key(self, kind: Kind) -> dict[str, Record]:
        return {key: r for r in self.records.get(kind, []) for _, key in r.keys}


def external_key(name: str, value: object) -> str:
    text = n.text_or_none(value)
    if text is None:
        raise RowRejectedError("REJ-03", name)
    return f"{name}:{text}"


class _Row:
    """Accès aux champs canoniques d'une ligne via la correspondance."""

    def __init__(self, entity: EntitySpec, row: SourceRow) -> None:
        self.entity = entity
        self.row = row

    def raw(self, canonical: str) -> object:
        if canonical in self.entity.constants:
            return self.entity.constants[canonical]
        column = self.entity.fields.get(canonical)
        return None if column is None else self.row.get(column)

    def has(self, canonical: str) -> bool:
        return canonical in self.entity.fields or canonical in self.entity.constants


def _row_label(entity: EntitySpec, row: SourceRow, index: int) -> str:
    try:
        return external_key(entity.keys[0].name, row.get(entity.keys[0].column))
    except RowRejectedError:
        return f"ligne:{index + 1}"


def _currency(row: _Row, declared: str) -> None:
    if row.has("currency") and n.required_text(row.raw("currency"), "currency") != declared:
        raise RowRejectedError("REJ-07", "currency")


type Builder = Callable[[_Row, "Context"], Record]


@dataclass(frozen=True, slots=True)
class Context:
    spec: ImportSpec
    currency: str
    staged: Staged


def _keys(entity: EntitySpec, row: SourceRow) -> tuple[tuple[str, str], ...]:
    return tuple((k.name, external_key(k.name, row.get(k.column))) for k in entity.keys)


def _refs(entity: EntitySpec, row: SourceRow) -> dict[str, tuple[Kind, str]]:
    return {
        role: (ref.kind, external_key(ref.key, row.get(ref.column)))
        for role, ref in entity.refs.items()
    }


def _plan(row: _Row, ctx: Context) -> dict[str, object]:
    return {
        "code": n.to_code(row.raw("code"), "code", PLAN_CODE),
        "name": n.required_text(row.raw("name"), "name"),
    }


def _plan_version(row: _Row, ctx: Context) -> dict[str, object]:
    _currency(row, ctx.currency)
    valid_from = n.to_date(row.raw("valid_from"), "valid_from")
    valid_to = n.to_optional_date(row.raw("valid_to"), "valid_to")
    if valid_to is not None and valid_to < valid_from:
        raise RowRejectedError("REJ-05", "valid_to")
    return {
        "valid_from": valid_from,
        "valid_to": valid_to,
        "coverage_rate_bp": n.percent_to_bp(
            row.raw("coverage_rate_percent"), "coverage_rate_percent"
        ),
        "family_annual_ceiling_xof": n.to_xof(
            row.raw("family_annual_ceiling"), "family_annual_ceiling"
        ),
        "waiting_period_days": n.to_int(row.raw("waiting_period_days"), "waiting_period_days"),
        "monthly_contribution_xof": n.to_xof(
            row.raw("monthly_contribution"), "monthly_contribution"
        ),
    }


def _coverage(row: _Row, ctx: Context) -> dict[str, object]:
    _currency(row, ctx.currency)
    limit = row.raw("annual_limit")
    return {
        "category": n.to_category(row.raw("category"), "category"),
        "label": n.required_text(row.raw("label"), "label"),
        "annual_limit_xof": None if n.text_or_none(limit) is None else n.to_xof(limit, "limit"),
    }


def _provider(row: _Row, ctx: Context) -> dict[str, object]:
    vocab = ctx.spec.vocabularies
    return {
        "name": n.required_text(row.raw("name"), "name"),
        "kind": n.in_vocabulary(row.raw("kind"), "kind", vocab["provider_kind"]),
        "city": n.required_text(row.raw("city"), "city"),
        "country_code": n.in_vocabulary(row.raw("country"), "country", vocab["country"]),
        "status": n.in_vocabulary(row.raw("status"), "status", vocab["provider_status"]),
    }


def _person(row: _Row, prefix: str = "") -> tuple[PersonData, bool]:
    phone_raw = row.raw("phone") if row.has("phone") else None
    phone = n.to_e164(phone_raw, row.raw("phone_country_code"))
    return (
        PersonData(
            given_name=n.required_text(row.raw("given_name"), f"{prefix}given_name"),
            family_name=n.required_text(row.raw("family_name"), f"{prefix}family_name"),
            birth_date=n.to_date(row.raw("birth_date"), f"{prefix}birth_date"),
            phone_e164=phone,
        ),
        n.text_or_none(phone_raw) is not None and phone is None,
    )


def _contribution(row: _Row, ctx: Context) -> dict[str, object]:
    _currency(row, ctx.currency)
    paid_on = n.to_date(row.raw("paid_on"), "paid_on")
    return {
        "amount_xof": n.to_xof(row.raw("amount"), "amount"),
        "period_start": paid_on.replace(day=1),
        "paid_on": paid_on,
    }


def _claim(row: _Row, ctx: Context, status: str) -> dict[str, object]:
    _currency(row, ctx.currency)
    total = n.to_xof(row.raw("total"), "total")
    covered_raw = row.raw("covered")
    if n.text_or_none(covered_raw) is None:
        if status in {"accordee", "payee"}:
            raise RowRejectedError("REJ-03", "covered")
        covered = 0
    else:
        covered = n.to_xof(covered_raw, "covered")
    if covered > total:
        raise RowRejectedError("REJ-02", "covered")
    if status == "refusee":
        covered = 0
    return {
        "service_date": n.to_date(row.raw("service_date"), "service_date"),
        "status": status,
        "total_xof": total,
        "covered_xof": covered,
    }


_SIMPLE: Final[Mapping[Kind, Callable[[_Row, Context], dict[str, object]]]] = {
    "plan": _plan,
    "plan_version": _plan_version,
    "coverage": _coverage,
    "provider": _provider,
}


def _status(entity: EntitySpec, row: _Row) -> str | Excluded:
    assert entity.status_vocabulary is not None  # garanti par validate_spec
    outcome = lookup(STATUS_MAP, entity.status_vocabulary, row.raw("status"), "status")
    return outcome if isinstance(outcome, Excluded) else outcome.value


def _json_dependents(
    entity: EntitySpec, row: _Row, member_key: tuple[str, str], ctx: Context
) -> list[Record]:
    spec = entity.json_dependents
    raw = row.raw("beneficiaries_json") if row.has("beneficiaries_json") else None
    if spec is None or n.text_or_none(raw) is None:
        return []
    try:
        items = json.loads(raw) if isinstance(raw, str | bytes) else raw
    except json.JSONDecodeError:
        raise RowRejectedError("REJ-05", "beneficiaries_json") from None
    if not isinstance(items, list) or len(items) > _MAX_ROWS_PER_DEPENDENT_LIST:
        raise RowRejectedError("REJ-05", "beneficiaries_json")
    key_name = f"{member_key[0]}_beneficiary"[:40]
    value = member_key[1].split(":", 1)[1]
    relationships = dict(ctx.spec.vocabularies["relationship"])
    records = []
    for position, item in enumerate(items, start=1):
        key = f"{key_name}:{value}#{position}"
        try:
            if not isinstance(item, dict):
                raise RowRejectedError("REJ-05", "beneficiaries_json")
            person = PersonData(
                given_name=n.required_text(item.get(spec.given_name), "beneficiary.given_name"),
                family_name=n.required_text(
                    item.get(spec.family_name), "beneficiary.family_name"
                ),
                birth_date=n.to_date(item.get(spec.birth_date), "beneficiary.birth_date"),
                phone_e164=None,
            )
            relationship = n.in_vocabulary(
                item.get(spec.relationship), "beneficiary.relationship", relationships
            )
        except RowRejectedError as rejected:
            ctx.staged.rejections.append(
                Rejection(entity.dataset.name, key, rejected.code, rejected.field)
            )
            continue
        records.append(
            Record(
                kind="dependent",
                keys=((key_name, key),),
                values={"person": person, "relationship": relationship},
                refs={"member": ("member", member_key[1])},
            )
        )
    return records


def _member(row: _Row, entity: EntitySpec, ctx: Context, index: int) -> list[Record]:
    status = _status(entity, row)
    keys = _keys(entity, row.row)
    if isinstance(status, Excluded):  # aucune exclusion d'adhérent aujourd'hui
        ctx.staged.exclusions.append(Exclusion(entity.dataset.name, keys[0][1], status.code))
        return []
    person, phone_dropped = _person(row)
    if phone_dropped:
        ctx.staged.warnings.append(Rejection(entity.dataset.name, keys[0][1], "W-01", "phone"))
    member = Record(
        kind="member",
        keys=keys,
        values={
            "person": person,
            "enrolled_on": n.to_date(row.raw("enrolled_on"), "enrolled_on"),
            "status": IMPORTED_MEMBER_STATUS,
            "email": n.normalize_email(row.raw("email")) if row.has("email") else None,
        },
        refs=_refs(entity, row.row),
        person_keys=tuple(
            (k.name, external_key(k.name, row.row.get(k.column))) for k in entity.person_keys
        ),
        import_status=status,
    )
    try:
        dependents = _json_dependents(entity, row, keys[0], ctx)
    except RowRejectedError as rejected:  # liste illisible : l'adhérent reste, la liste non
        ctx.staged.rejections.append(
            Rejection(entity.dataset.name, keys[0][1], rejected.code, rejected.field)
        )
        dependents = []
    return [member, *dependents]


def _build(entity: EntitySpec, row: _Row, ctx: Context, index: int) -> list[Record]:
    kind = entity.kind
    if kind == "member":
        return _member(row, entity, ctx, index)
    keys = _keys(entity, row.row)
    refs = _refs(entity, row.row)
    if kind in _SIMPLE:
        return [Record(kind, keys, _SIMPLE[kind](row, ctx), refs)]
    if kind == "dependent":
        person, _ = _person(row)
        relationship = n.in_vocabulary(
            row.raw("relationship"), "relationship", dict(ctx.spec.vocabularies["relationship"])
        )
        return [Record(kind, keys, {"person": person, "relationship": relationship}, refs)]
    status = _status(entity, row)
    if isinstance(status, Excluded):
        ctx.staged.exclusions.append(Exclusion(entity.dataset.name, keys[0][1], status.code))
        return []
    if kind == "contribution":
        return [Record(kind, keys, _contribution(row, ctx), refs)]
    return [Record(kind, keys, _claim(row, ctx, status), refs)]


def _reject_duplicate_keys(kind: Kind, staged: Staged, dataset: str) -> None:
    records = staged.records.get(kind, [])
    counts = Counter(key for r in records for _, key in r.keys)
    duplicated = {key for key, count in counts.items() if count > 1}
    if not duplicated:
        return
    keep = []
    for record in records:
        if any(key in duplicated for _, key in record.keys):
            staged.rejections.append(Rejection(dataset, record.primary, "REJ-08", "cle"))
        else:
            keep.append(record)
    staged.records[kind] = keep


type Verdict = tuple[str, str] | None


def _reject_where(
    staged: Staged, kind: Kind, dataset: str, predicate: Callable[[Record], Verdict]
) -> bool:
    """Rejette les lignes pour lesquelles ``predicate`` rend (code, champ) ; True si changement."""
    keep, changed = [], False
    for record in staged.records.get(kind, []):
        verdict = predicate(record)
        if verdict is None:
            keep.append(record)
        else:
            staged.rejections.append(Rejection(dataset, record.primary, *verdict))
            changed = True
    staged.records[kind] = keep
    return changed


def _plan_version_at(staged: Staged, plan_key: str, day: date) -> Record | None:
    plans = staged.by_key("plan")
    plan = plans.get(plan_key)
    if plan is None:
        return None
    plan_keys = {key for _, key in plan.keys}
    candidates = [
        v
        for v in staged.records.get("plan_version", [])
        if v.refs["plan"][1] in plan_keys
        and v.values["valid_from"] <= day  # type: ignore[operator]
        and (v.values["valid_to"] is None or day <= v.values["valid_to"])  # type: ignore[operator]
    ]
    if len(candidates) != 1:
        return None  # aucune version, ou plusieurs qui se chevauchent : choix humain
    return candidates[0]


def _keysets(staged: Staged) -> dict[Kind, set[str]]:
    return {kind: set(staged.by_key(kind)) for kind in list(staged.records)}


def _cross_checks(spec: ImportSpec, staged: Staged) -> None:
    """Références, une personne = un contrat, un mois = une cotisation ; jusqu'au point fixe."""
    datasets: dict[Kind, str] = {kind: e.dataset.name for kind, e in spec.entities.items()}
    datasets.setdefault("dependent", datasets["member"])
    # Une personne ne porte qu'un contrat dans One (members UNIQUE (organisation, personne)).
    persons = Counter(r.person_keys[0][1] for r in staged.records.get("member", []))
    _reject_where(
        staged,
        "member",
        datasets["member"],
        lambda r: ("REJ-11", "personne") if persons[r.person_keys[0][1]] > 1 else None,
    )
    if "contribution" in spec.entities:
        months = Counter(
            (r.refs["member"][1], r.values["period_start"])
            for r in staged.records.get("contribution", [])
        )
        _reject_where(
            staged,
            "contribution",
            datasets["contribution"],
            lambda r: ("REJ-11", "paid_on")
            if months[(r.refs["member"][1], r.values["period_start"])] > 1
            else None,
        )
    changed = True
    while changed:
        changed = False
        for kind in (k for k in LOAD_ORDER if k in staged.records):
            known = _keysets(staged)

            def dangling(record: Record, known: dict[Kind, set[str]] = known) -> Verdict:
                for role, (target, key) in record.refs.items():
                    if key not in known.get(target, set()):
                        return ("REJ-04", role)
                return None

            changed |= _reject_where(staged, kind, datasets[kind], dangling)
        changed |= _reject_where(
            staged,
            "member",
            datasets["member"],
            lambda r: None
            if _plan_version_at(staged, r.refs["plan"][1], r.values["enrolled_on"])  # type: ignore[arg-type]
            else ("REJ-04", "plan_version"),
        )
        if "claim" in spec.entities:
            changed |= _reject_where(
                staged, "claim", datasets["claim"], lambda r: _claim_version(staged, r)
            )


def _claim_version(staged: Staged, record: Record) -> Verdict:
    member = staged.by_key("member").get(record.refs["member"][1])
    if member is None:
        return ("REJ-04", "member")
    day = record.values["service_date"]
    version = _plan_version_at(staged, member.refs["plan"][1], day)  # type: ignore[arg-type]
    return None if version is not None else ("REJ-04", "plan_version")


def _probable_duplicates(staged: Staged) -> None:
    groups: dict[str, list[str]] = defaultdict(list)
    for record in staged.records.get("member", []):
        email = record.values.get("email")
        if isinstance(email, str):
            groups[email].append(record.primary)
    staged.probable_duplicates = sorted(tuple(sorted(g)) for g in groups.values() if len(g) > 1)


def _rows(entity: EntitySpec, snapshot: SourceSnapshot, staged: Staged) -> Iterable[SourceRow]:
    for row in snapshot.rows(entity.dataset.name):
        if all(n.text_or_none(row.get(c)) in allowed for c, allowed in entity.only_when.items()):
            yield row
        else:
            staged.filtered[entity.dataset.name] += 1


def transform(snapshot: SourceSnapshot, spec: ImportSpec, currency: str) -> Staged:
    """Normalise toute la source ; aucune ligne n'est perdue sans motif."""
    staged = Staged()
    ctx = Context(spec=spec, currency=currency, staged=staged)
    for kind, entity in spec.entities.items():
        for index, source_row in enumerate(_rows(entity, snapshot, staged)):
            try:
                for record in _build(entity, _Row(entity, source_row), ctx, index):
                    staged.records[record.kind].append(record)
            except RowRejectedError as rejected:
                staged.rejections.append(
                    Rejection(
                        entity.dataset.name,
                        _row_label(entity, source_row, index),
                        rejected.code,
                        rejected.field,
                    )
                )
        _reject_duplicate_keys(kind, staged, entity.dataset.name)
    _reject_duplicate_keys("dependent", staged, spec.entities["member"].dataset.name)
    _cross_checks(spec, staged)
    _probable_duplicates(staged)
    return staged
