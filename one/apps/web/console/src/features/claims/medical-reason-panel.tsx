"use client";

import { EyeIcon, EyeOffIcon, LockIcon } from "lucide-react";
import { useAccess, useReadMedicalReason } from "@/api/queries";
import { ErrorState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { t } from "@/i18n";
import { formatDateTime } from "@/lib/format";

/**
 * Motif médical (R6). Le gestionnaire ne voit qu'un bloc masqué et aucune requête n'est émise.
 * Le médecin-conseil le lit à la demande chez HealthOS ; chaque lecture est journalisée
 * côté API et la trace d'audit est affichée. Le motif n'est jamais mis en cache.
 */
export function MedicalReasonPanel({ claimId }: { claimId: string }) {
  const { has, timezone } = useAccess();
  const read = useReadMedicalReason(claimId);

  if (!has("medecin_conseil")) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed border-line-2 px-3 py-2.5 text-xs text-fg-2">
        <LockIcon className="size-3.5 shrink-0" aria-hidden />
        <span>{t("medical.maskedGestionnaire")}</span>
      </div>
    );
  }

  return (
    <section aria-labelledby="medical-title" className="flex flex-col gap-2">
      <h3 id="medical-title" className="eyebrow">
        {t("medical.title")}
      </h3>
      {read.data ? (
        <div className="flex flex-col gap-1.5 rounded-md border border-line bg-sunk p-3">
          <p>{read.data.text}</p>
          <p data-testid="medical-audit" className="text-xs text-fg-2">
            {t("medical.auditTrace", { date: formatDateTime(read.data.read_at, timezone), id: read.data.audit_event_id })}
          </p>
          <div>
            <Button variant="ghost" size="sm" onClick={() => read.reset()}>
              <EyeOffIcon aria-hidden />
              {t("medical.hide")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-start gap-1.5">
          <Button variant="outline" onClick={() => read.mutate()} disabled={read.isPending}>
            <EyeIcon aria-hidden />
            {read.isPending ? t("medical.reading") : t("medical.readButton")}
          </Button>
          <p className="text-xs text-fg-2">{t("medical.readHint")}</p>
        </div>
      )}
      {read.isError ? <ErrorState error={read.error} /> : null}
    </section>
  );
}
