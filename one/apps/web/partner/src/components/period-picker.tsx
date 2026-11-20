"use client";

import { t, tDynamic } from "@/i18n";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/cn";

/** Semaines entières terminées : 1, 4, 13 et 52 (CR-P3-02 : la période demandée est la période publiée). */
export const PERIODS = [1, 4, 13, 52] as const;
export type PeriodWeeks = (typeof PERIODS)[number];

/** Choix de la période en semaines entières terminées ; la période retenue est écrite en clair. */
export function PeriodPicker({ weeks, onChange, from, to }: { weeks: PeriodWeeks; onChange: (weeks: PeriodWeeks) => void; from: string; to: string }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div role="group" aria-label={t("period.label")} className="flex flex-wrap gap-1.5">
        {PERIODS.map((p) => (
          <button
            key={p}
            type="button"
            aria-pressed={weeks === p}
            onClick={() => onChange(p)}
            className={cn(
              "min-h-12 rounded-full border px-4 text-dense font-medium",
              weeks === p ? "border-accent bg-accent-2 text-fg" : "border-line-2 bg-surface text-fg hover:bg-sunk",
            )}
          >
            {tDynamic("period.preset", String(p))}
          </button>
        ))}
      </div>
      <span className="text-dense text-fg-2" data-testid="period-range">
        {t("period.range", { from: formatDate(from), to: formatDate(to) })}
      </span>
    </div>
  );
}
