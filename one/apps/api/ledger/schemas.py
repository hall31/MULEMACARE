"""Schémas HTTP des opérations L3, alignés sur ``components.schemas`` de specs/openapi.yaml."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.ledger.accounts import Account
from api.ledger.domain import Balance, EntryPage, PostedEntry

AmountXof = int  # entier FCFA (int64), jamais de flottant


class LedgerAccount(BaseModel):
    code: str = Field(pattern=r"^[0-9]{4,8}$")
    label: str
    account_class: Literal["actif", "passif", "charge", "produit"]


class LedgerAccountList(BaseModel):
    items: list[LedgerAccount]


class LedgerLine(BaseModel):
    line_no: int = Field(ge=1)
    account_code: str
    account_label: str
    debit_xof: AmountXof = Field(ge=0)
    credit_xof: AmountXof = Field(ge=0)
    provider_id: UUID | None = None
    member_id: UUID | None = None


class LedgerEntry(BaseModel):
    id: UUID
    entry_number: str
    accounting_date: date
    posted_at: datetime
    label: str
    source_type: Literal["prise_en_charge", "cotisation", "reglement", "contre_passation"]
    source_id: UUID | None = None
    reverses_entry_id: UUID | None = None
    reversed_by_entry_id: UUID | None = None
    currency: Literal["XOF"] = "XOF"
    lines: list[LedgerLine] = Field(min_length=2)


class PageInfo(BaseModel):
    next_cursor: str | None


class LedgerEntryList(BaseModel):
    items: list[LedgerEntry]
    page: PageInfo


class ReverseLedgerEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=200)


class LedgerBalanceRow(BaseModel):
    account_code: str
    account_label: str
    debit_xof: AmountXof = Field(ge=0)
    credit_xof: AmountXof = Field(ge=0)


class LedgerBalance(BaseModel):
    at: date
    currency: Literal["XOF"] = "XOF"
    rows: list[LedgerBalanceRow]
    total_debit_xof: AmountXof = Field(ge=0)
    total_credit_xof: AmountXof = Field(ge=0)


def account_out(account: Account) -> LedgerAccount:
    return LedgerAccount(
        code=account.code, label=account.label, account_class=account.account_class
    )


def entry_out(entry: PostedEntry) -> LedgerEntry:
    return LedgerEntry(
        id=entry.id,
        entry_number=entry.entry_number,
        accounting_date=entry.accounting_date,
        posted_at=entry.posted_at,
        label=entry.label,
        source_type=entry.source_type,
        source_id=entry.source_id,
        reverses_entry_id=entry.reverses_entry_id,
        reversed_by_entry_id=entry.reversed_by_entry_id,
        lines=[
            LedgerLine(
                line_no=line.line_no,
                account_code=line.account_code,
                account_label=line.account_label,
                debit_xof=line.debit_xof,
                credit_xof=line.credit_xof,
                provider_id=line.provider_id,
                member_id=line.member_id,
            )
            for line in entry.lines
        ],
    )


def page_out(page: EntryPage) -> LedgerEntryList:
    return LedgerEntryList(
        items=[entry_out(entry) for entry in page.items],
        page=PageInfo(next_cursor=page.next_cursor),
    )


def balance_out(balance: Balance) -> LedgerBalance:
    return LedgerBalance(
        at=balance.at,
        rows=[
            LedgerBalanceRow(
                account_code=row.account_code,
                account_label=row.account_label,
                debit_xof=row.debit_xof,
                credit_xof=row.credit_xof,
            )
            for row in balance.rows
        ],
        total_debit_xof=balance.total_debit_xof,
        total_credit_xof=balance.total_credit_xof,
    )
