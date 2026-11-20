"use client";

import type { Entitlements } from "@/api/types";
import { t } from "@/i18n";
import { formatDateOnly, formatXof, formatXofParts, usedPercent } from "@/lib/format";

/**
 * Plafond familial restant, en entiers FCFA (Entitlements de getMyCard). La jauge est un décor :
 * la valeur est toujours écrite à côté (contrat §5).
 */
export function CeilingPanel({ entitlements }: { entitlements: Entitlements }) {
  const percent = usedPercent(entitlements.consumed_xof, entitlements.family_annual_ceiling_xof);
  const label = t("percent", { value: percent });
  const { number } = formatXofParts(entitlements.remaining_xof);
  return (
    <section className="panel" aria-labelledby="ceiling-t" data-testid="ceiling">
      <div className="panel-h">
        <h2 className="panel-t" id="ceiling-t">
          {t("ceiling.title")}
        </h2>
        <span className="amount">{label}</span>
      </div>
      <div className="pad stack">
        <p className="big">
          <span className="amount" data-testid="ceiling-remaining">
            {number}
          </span>
          <small>{t("ceiling.remainingUnit")}</small>
        </p>
        <div className="meter" role="img" aria-label={t("ceiling.meter", { value: label })}>
          <i style={{ width: `${percent}%` }} />
        </div>
        <p>
          {t("ceiling.used", { used: formatXof(entitlements.consumed_xof), ceiling: formatXof(entitlements.family_annual_ceiling_xof) })}
        </p>
        <p>{t("ceiling.at", { date: formatDateOnly(entitlements.at) })}</p>
      </div>
    </section>
  );
}
