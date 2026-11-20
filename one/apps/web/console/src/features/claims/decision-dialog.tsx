"use client";

import { useState } from "react";
import { toast } from "sonner";
import { newIdempotencyKey, useDecideClaim } from "@/api/queries";
import type { ClaimDecisionKind, ClaimSummary } from "@/api/types";
import { ErrorState } from "@/components/states";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/misc";
import { t, tDynamic } from "@/i18n";
import { DECISION_REASONS } from "@/lib/decision-reasons";
import { formatMoney } from "@/lib/format";

const ACTIONS: { decision: ClaimDecisionKind; label: "decision.approve" | "decision.requestDocuments" | "decision.reject"; variant: "default" | "outline" | "danger" }[] = [
  { decision: "accorder", label: "decision.approve", variant: "default" },
  { decision: "demander_pieces", label: "decision.requestDocuments", variant: "outline" },
  { decision: "refuser", label: "decision.reject", variant: "danger" },
];

/**
 * Décision humaine sur un dossier en revue (R5). Aucun champ texte libre : un motif codé
 * seulement, pour qu'aucune donnée médicale n'entre dans la base assurance.
 */
export function DecisionActions({ claim }: { claim: ClaimSummary }) {
  const [open, setOpen] = useState<ClaimDecisionKind | null>(null);

  return (
    <section aria-labelledby="decision-title" className="flex flex-col gap-2 border-t border-line pt-4">
      <h3 id="decision-title" className="eyebrow">
        {t("decision.actionsLabel")}
      </h3>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((a) => (
          <Button key={a.decision} variant={a.variant} onClick={() => setOpen(a.decision)}>
            {t(a.label)}
          </Button>
        ))}
      </div>
      {open ? <DecisionDialog claim={claim} decision={open} onClose={() => setOpen(null)} /> : null}
    </section>
  );
}

function DecisionDialog({ claim, decision, onClose }: { claim: ClaimSummary; decision: ClaimDecisionKind; onClose: () => void }) {
  const reasons = DECISION_REASONS[decision];
  const [reason, setReason] = useState<string>(reasons[0] ?? "");
  // Une clé par ouverture : un double clic ou un nouvel essai rejoue la même commande.
  const [idempotencyKey] = useState(newIdempotencyKey);
  const decide = useDecideClaim(claim.id);
  const number = claim.claim_number;

  const submit = async () => {
    try {
      // mutateAsync : la promesse aboutit même si le dossier, mis à jour, démonte ce dialogue.
      await decide.mutateAsync({ decision, reasonCode: reason, idempotencyKey });
    } catch {
      return; // l'erreur (Problem) est affichée dans le dialogue
    }
    toast.success(tDynamic("decision.success", decision, { number }));
    onClose();
  };

  return (
    <AlertDialog open onOpenChange={(next) => (!next && !decide.isPending ? onClose() : undefined)}>
      <AlertDialogContent>
        <AlertDialogTitle>{tDynamic("decision.dialogTitle", decision, { number })}</AlertDialogTitle>
        <AlertDialogDescription>
          {tDynamic("decision.dialogBody", decision, { amount: formatMoney(claim.covered_xof) })}
        </AlertDialogDescription>
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 font-medium">{t("decision.reasonLegend")}</legend>
          <RadioGroup value={reason} onValueChange={setReason}>
            {reasons.map((code) => (
              <div key={code} className="flex items-center gap-2.5">
                <RadioGroupItem value={code} id={`reason-${code}`} />
                <label htmlFor={`reason-${code}`} className="flex items-baseline gap-2">
                  <span>{tDynamic("decisionReasons", code)}</span>
                  <span className="tabular text-xs text-fg-2">{code}</span>
                </label>
              </div>
            ))}
          </RadioGroup>
          <p className="text-xs text-fg-2">{t("decision.reasonHint")}</p>
        </fieldset>
        {decide.isError ? <ErrorState error={decide.error} /> : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={decide.isPending}>{t("common.cancel")}</AlertDialogCancel>
          <Button
            variant={decision === "refuser" ? "danger" : "default"}
            onClick={() => void submit()}
            disabled={decide.isPending || !reason}
          >
            {decide.isPending ? t("decision.pending") : tDynamic("decision.confirm", decision)}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
