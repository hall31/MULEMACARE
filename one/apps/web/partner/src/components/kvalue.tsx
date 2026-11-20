import type { KAnonymousValue } from "@/api/types";
import { t } from "@/i18n";
import { isAvailable, tierLabel } from "@/lib/kanon";
import { cn } from "@/lib/cn";
import { Icon } from "./ui";

/** Valeur k-anonyme : la valeur formatée, ou « Masqué » (moins de 5 personnes), jamais un effectif exact. */
export function KValue({ value, format, className }: { value: KAnonymousValue; format: (v: number) => string; className?: string }) {
  if (!isAvailable(value)) {
    return (
      <span className={cn("inline-flex items-center gap-1.5 font-semibold text-fg-2", className)} data-masked="true">
        <Icon name="lock" className="size-3.5" />
        {t("kanon.masked")}
      </span>
    );
  }
  return <span className={cn("num font-semibold", className)}>{format(value.value)}</span>;
}

/** Effectif porteur, par palier (« 50 à 99 personnes »), ou la raison du masque. */
export function KTier({ value, className }: { value: KAnonymousValue; className?: string }) {
  const tier = isAvailable(value) ? tierLabel(value.contributors) : null;
  return <span className={cn("text-caption text-fg-2", className)}>{tier ? t("kanon.carriedBy", { tier }) : t("kanon.maskedHint")}</span>;
}

/** Indicateur clé : libellé, valeur (ou masqué), palier d'effectif. */
export function KpiCard({ label, value, format, hint, testId }: { label: string; value: KAnonymousValue; format: (v: number) => string; hint?: string; testId?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-line bg-surface p-4" data-testid={testId} data-status={value.status}>
      <span className="text-dense font-medium text-fg-2">{label}</span>
      <KValue value={value} format={format} className="text-title" />
      <KTier value={value} />
      {hint ? <span className="text-caption text-fg-2">{hint}</span> : null}
    </div>
  );
}
