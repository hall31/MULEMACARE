"use client";

import { LockIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Fragment, useMemo } from "react";
import { useAccess, useLedgerAccounts, useLedgerBalance, useLedgerEntries } from "@/api/queries";
import type { LedgerEntry } from "@/api/types";
import { RequireRole } from "@/components/require-role";
import { EmptyState, ErrorState, LoadingRows, PageHeader, Panel } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/misc";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { t, tDynamic } from "@/i18n";
import { cn } from "@/lib/cn";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";

/** Grand livre en lecture seule (R7 côté interface) : aucune action d'écriture n'est proposée. */
export function LedgerView() {
  return (
    <RequireRole roles={["gestionnaire", "admin"]}>
      <LedgerContent />
    </RequireRole>
  );
}

function LedgerContent() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const account = params.get("compte") ?? undefined;
  const accounts = useLedgerAccounts();
  const entries = useLedgerEntries(account);
  const balance = useLedgerBalance();
  const { timezone } = useAccess();
  const items = useMemo(() => entries.data?.pages.flatMap((p) => p.items) ?? [], [entries.data]);
  const byId = useMemo(() => new Map(items.map((e) => [e.id, e])), [items]);

  const setAccount = (code: string) => {
    const next = new URLSearchParams(params.toString());
    if (code) next.set("compte", code);
    else next.delete("compte");
    const qs = next.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  return (
    <>
      <PageHeader eyebrow={t("ledger.eyebrow")} title={t("ledger.title")} />
      <p className="flex items-center gap-2.5 rounded-md bg-sunk px-3.5 py-2.5 text-[13px]">
        <LockIcon className="size-4 shrink-0 text-fg-2" aria-hidden />
        {t("ledger.appendOnly")}
      </p>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Panel>
          <div className="flex items-center gap-3 border-b border-line px-4 py-3">
            <label htmlFor="ledger-account" className="text-[13px] font-medium">
              {t("ledger.accountFilter")}
            </label>
            <NativeSelect id="ledger-account" className="w-auto min-w-56" value={account ?? ""} onChange={(e) => setAccount(e.target.value)}>
              <option value="">{t("ledger.allAccounts")}</option>
              {accounts.data?.items.map((a) => (
                <option key={a.code} value={a.code}>
                  {a.code} · {a.label}
                </option>
              ))}
            </NativeSelect>
          </div>
          {entries.isPending ? <LoadingRows /> : null}
          {entries.isError ? (
            <div className="p-4">
              <ErrorState error={entries.error} onRetry={() => void entries.refetch()} />
            </div>
          ) : null}
          {entries.isSuccess && items.length === 0 ? (
            <EmptyState
              title={t("ledger.emptyTitle")}
              body={t("ledger.emptyBody")}
              next={account ? t("emptyNext.ledgerAccount") : undefined}
              action={
                account ? (
                  <Button variant="outline" size="sm" onClick={() => setAccount("")}>
                    {t("emptyNext.showAllAccounts")}
                  </Button>
                ) : undefined
              }
            />
          ) : null}
          {items.length > 0 ? (
            <Table aria-label={t("ledger.tableLabel")}>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("ledger.colEntry")}</TableHead>
                  <TableHead>{t("ledger.colLabel")}</TableHead>
                  <TableHead>{t("ledger.colAccount")}</TableHead>
                  <TableHead className="text-right">{t("ledger.colDebit")}</TableHead>
                  <TableHead className="text-right">{t("ledger.colCredit")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((entry) => (
                  <EntryRows key={entry.id} entry={entry} timezone={timezone} reversed={entry.reverses_entry_id ? byId.get(entry.reverses_entry_id) : undefined} />
                ))}
              </TableBody>
            </Table>
          ) : null}
          {entries.hasNextPage ? (
            <div className="border-t border-line p-3">
              <Button variant="outline" size="sm" onClick={() => void entries.fetchNextPage()} disabled={entries.isFetchingNextPage}>
                {t("common.loadMore")}
              </Button>
            </div>
          ) : null}
        </Panel>

        <Panel aria-labelledby="balance-title" className="self-start">
          <div className="flex items-center gap-2.5 border-b border-line px-4 py-3">
            <h2 id="balance-title" className="text-[15px] font-semibold">
              {balance.data ? t("ledger.balanceTitle", { date: formatDate(balance.data.at) }) : t("ledger.balanceTitle", { date: t("common.none") })}
            </h2>
          </div>
          {balance.isPending ? <LoadingRows rows={4} /> : null}
          {balance.isError ? (
            <div className="p-4">
              <ErrorState error={balance.error} onRetry={() => void balance.refetch()} />
            </div>
          ) : null}
          {balance.data ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("ledger.colAccount")}</TableHead>
                  <TableHead className="text-right">{t("ledger.colDebit")}</TableHead>
                  <TableHead className="text-right">{t("ledger.colCredit")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {balance.data.rows.map((r) => (
                  <TableRow key={r.account_code}>
                    <TableCell>
                      <span className="tabular text-xs">{r.account_code}</span> <span className="text-fg-2">{r.account_label}</span>
                    </TableCell>
                    <TableCell className="tabular text-right">{formatMoney(r.debit_xof, { unit: false })}</TableCell>
                    <TableCell className="tabular text-right">{formatMoney(r.credit_xof, { unit: false })}</TableCell>
                  </TableRow>
                ))}
                <TableRow>
                  <TableCell className="border-t border-line-2">
                    <span className="font-semibold">{t("ledger.balanceTotal")}</span>{" "}
                    <Badge
                      data-testid="balance-status"
                      tone={balance.data.total_debit_xof === balance.data.total_credit_xof ? "ok" : "crit"}
                    >
                      {balance.data.total_debit_xof === balance.data.total_credit_xof ? t("ledger.balanced") : t("ledger.unbalanced")}
                    </Badge>
                  </TableCell>
                  <TableCell className="tabular border-t border-line-2 text-right font-semibold">
                    {formatMoney(balance.data.total_debit_xof, { unit: false })}
                  </TableCell>
                  <TableCell className="tabular border-t border-line-2 text-right font-semibold">
                    {formatMoney(balance.data.total_credit_xof, { unit: false })}
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          ) : null}
        </Panel>
      </div>
    </>
  );
}

function EntryRows({ entry, timezone, reversed }: { entry: LedgerEntry; timezone: string; reversed: LedgerEntry | undefined }) {
  return (
    <Fragment>
      {entry.lines.map((line, i) => (
        <TableRow key={line.line_no} className={cn(i === 0 && "[&>td]:border-t [&>td]:border-t-line-2")}>
          {i === 0 ? (
            <>
              <TableCell rowSpan={entry.lines.length} className="align-top whitespace-nowrap">
                <div className="tabular text-xs">{entry.entry_number}</div>
                <div className="text-xs text-fg-2">{formatDateTime(entry.posted_at, timezone)}</div>
              </TableCell>
              <TableCell rowSpan={entry.lines.length} className="align-top">
                <div>{entry.label}</div>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  <span className="text-xs text-fg-2">{tDynamic("ledger.sourceType", entry.source_type)}</span>
                  {entry.reverses_entry_id ? (
                    <Badge tone="neutral" dot={false}>
                      {t("ledger.reversal", { number: reversed?.entry_number ?? t("common.none") })}
                    </Badge>
                  ) : null}
                  {entry.reversed_by_entry_id ? (
                    <Badge tone="neutral" dot={false}>
                      {t("ledger.reversedBy")}
                    </Badge>
                  ) : null}
                </div>
              </TableCell>
            </>
          ) : null}
          <TableCell>
            <span className="tabular text-xs">{line.account_code}</span> <span className="text-fg-2">{line.account_label}</span>
          </TableCell>
          <TableCell className="tabular text-right">{line.debit_xof ? formatMoney(line.debit_xof, { unit: false }) : ""}</TableCell>
          <TableCell className="tabular text-right">{line.credit_xof ? formatMoney(line.credit_xof, { unit: false }) : ""}</TableCell>
        </TableRow>
      ))}
    </Fragment>
  );
}
