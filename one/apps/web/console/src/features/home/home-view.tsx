"use client";

import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAccess, useClaims, useWorkQueue } from "@/api/queries";
import { EmptyState, ErrorState, LoadingRows, OpenPaletteButton, Panel } from "@/components/states";
import { ClaimStatusBadge } from "@/components/status-badges";
import { t, type MessageKey } from "@/i18n";
import { cn } from "@/lib/cn";
import { formatDateTime, formatLongDate, formatMoney } from "@/lib/format";
import type { Tone } from "@/lib/status";

interface TodoItem {
  count: number;
  label: MessageKey;
  hint: MessageKey;
  tone: Tone;
  href: string | null;
}

const SEVERITY: Record<Tone, string> = { crit: "bg-crit", warn: "bg-warn", ok: "bg-ok", info: "bg-info", neutral: "bg-line-2" };

/**
 * Accueil. Les compteurs viennent de GET /v1/work-queue, calculés sur les données réelles :
 * aucun indicateur saisi à la main ni extrapolé (PRD §1, « KPI fabriqués »).
 */
export function HomeView() {
  const { has, timezone, ready } = useAccess();
  const queue = useWorkQueue(ready);
  const recent = useClaims({ limit: 5 });
  const isManager = has("gestionnaire") || has("admin");
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);

  const hour = now ? Number(new Intl.DateTimeFormat("fr-FR", { hour: "numeric", hourCycle: "h23", timeZone: timezone }).format(now)) : 12;

  const todo: TodoItem[] = queue.data
    ? [
        { count: queue.data.fraud_alerts, label: "home.todoFraud", hint: "home.todoFraudHint", tone: "crit", href: "/prises-en-charge?fraude=1" },
        { count: queue.data.claims_in_review, label: "home.todoReview", hint: "home.todoReviewHint", tone: "warn", href: "/prises-en-charge?statut=en_revue" },
        {
          count: queue.data.members_unpaid_over_30_days,
          label: "home.todoUnpaid",
          hint: "home.todoUnpaidHint",
          tone: "warn",
          href: isManager ? "/adherents?statut=suspendu" : null,
        },
        { count: queue.data.auto_approved_today, label: "home.todoAuto", hint: "home.todoAutoHint", tone: "ok", href: "/prises-en-charge?statut=accordee_auto" },
      ]
    : [];

  const recentItems = recent.data?.pages[0]?.items ?? [];

  return (
    <>
      <section className="flex flex-col items-start gap-3 pt-4 pb-1">
        <span className="eyebrow">{now ? formatLongDate(now, timezone) : t("common.none")}</span>
        <h1 className="text-[26px] font-semibold">{hour >= 17 ? t("home.greetingEvening") : t("home.greetingMorning")}</h1>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel aria-labelledby="todo-title">
          <div className="flex items-center gap-2.5 border-b border-line px-4 py-3.5">
            <h2 id="todo-title" className="text-[17px] font-semibold">
              {t("home.todoTitle")}
            </h2>
            <span className="flex-1" />
            <span className="text-xs text-fg-2">{t("home.todoHint")}</span>
          </div>
          {queue.isPending ? <LoadingRows rows={4} /> : null}
          {queue.isError ? (
            <div className="p-4">
              <ErrorState error={queue.error} onRetry={() => void queue.refetch()} />
            </div>
          ) : null}
          <ul className="flex flex-col">
            {todo.map((item) => {
              const content = (
                <>
                  <span aria-hidden className={cn("w-[3px] self-stretch rounded-sm", SEVERITY[item.tone])} />
                  <span className="tabular min-w-11 text-right text-[13px]">{item.count}</span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span>{t(item.label)}</span>
                    <span className="text-xs text-fg-2">{t(item.hint)}</span>
                  </span>
                  {item.href ? <ArrowRightIcon className="size-4 text-fg-2" aria-hidden /> : null}
                </>
              );
              return (
                <li key={item.label} className="border-b border-line last:border-b-0">
                  {item.href ? (
                    <Link href={item.href} className="flex items-center gap-3 px-4 py-3 hover:bg-sunk">
                      {content}
                    </Link>
                  ) : (
                    <div className="flex items-center gap-3 px-4 py-3">{content}</div>
                  )}
                </li>
              );
            })}
          </ul>
        </Panel>

        <Panel aria-labelledby="recent-title">
          <div className="flex items-center gap-2.5 border-b border-line px-4 py-3.5">
            <h2 id="recent-title" className="text-[17px] font-semibold">
              {t("home.recentTitle")}
            </h2>
          </div>
          {recent.isPending ? <LoadingRows rows={4} /> : null}
          {recent.isError ? (
            <div className="p-4">
              <ErrorState error={recent.error} onRetry={() => void recent.refetch()} />
            </div>
          ) : null}
          {recent.isSuccess && recentItems.length === 0 ? <EmptyState title={t("home.recentEmpty")} next={t("emptyNext.recentEmpty")} action={<OpenPaletteButton />} /> : null}
          <ul className="flex flex-col">
            {recentItems.map((c) => (
              <li key={c.id} className="border-b border-line last:border-b-0">
                <Link href={`/prises-en-charge?dossier=${c.id}`} className="flex items-center gap-3 px-4 py-2.5 text-[13px] hover:bg-sunk">
                  <span className="tabular w-11 shrink-0 text-xs text-fg-2">{formatDateTime(c.requested_at, timezone).slice(11)}</span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate">{c.member_display_name}</span>
                    <span className="truncate text-xs text-fg-2">
                      <span className="tabular">{c.claim_number}</span> · {c.provider_name}
                    </span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-1">
                    <span className="tabular-nums">{formatMoney(c.total_xof)}</span>
                    <ClaimStatusBadge status={c.status} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="border-t border-line px-4 py-2.5">
            <Link href="/prises-en-charge" className="inline-flex items-center gap-1.5 text-[13px] font-medium text-brand hover:underline">
              {t("home.seeAll")}
              <ArrowRightIcon className="size-3.5" aria-hidden />
            </Link>
          </div>
        </Panel>
      </div>
    </>
  );
}
