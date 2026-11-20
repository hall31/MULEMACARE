"use client";

import { useAccess, useClaim } from "@/api/queries";
import type { ClaimDetail } from "@/api/types";
import { ErrorState, LoadingRows } from "@/components/states";
import { ClaimStatusBadge, FraudBadge } from "@/components/status-badges";
import { Sheet, SheetBody, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { t, tDynamic } from "@/i18n";
import { formatDate, formatDateTime, formatMoney } from "@/lib/format";
import { DecisionActions } from "./decision-dialog";
import { MedicalReasonPanel } from "./medical-reason-panel";

/** Tiroir du dossier : actes, montants, règle et version, historique des décisions, accord. */
export function ClaimDrawer({ claimId, onClose }: { claimId: string; onClose: () => void }) {
  const claim = useClaim(claimId);
  const number = claim.data?.claim.claim_number;

  return (
    <Sheet open onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <SheetContent aria-describedby={undefined}>
        <SheetTitle className="sr-only">
          {number ? t("claim.drawerLabel", { number }) : t("states.loading")}
        </SheetTitle>
        {claim.isPending ? <LoadingRows rows={6} /> : null}
        {claim.isError ? (
          <div className="p-5">
            <ErrorState error={claim.error} title={t("claim.loadError")} onRetry={() => void claim.refetch()} />
          </div>
        ) : null}
        {claim.data ? <ClaimDetailView detail={claim.data} /> : null}
      </SheetContent>
    </Sheet>
  );
}

function ClaimDetailView({ detail }: { detail: ClaimDetail }) {
  const { has, timezone } = useAccess();
  const c = detail.claim;
  const canDecide = has("medecin_conseil") && c.status === "en_revue";

  return (
    <>
      <SheetHeader>
        <p className="tabular text-xs text-fg-2">
          {c.claim_number} · {formatDateTime(c.requested_at, timezone)}
        </p>
        <p className="mt-1 font-display text-xl font-semibold tabular-nums">{formatMoney(c.total_xof)}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <ClaimStatusBadge status={c.status} data-testid="claim-status" />
          {c.fraud_flagged ? <FraudBadge /> : null}
        </div>
        <SheetDescription className="sr-only">{c.provider_name}</SheetDescription>
      </SheetHeader>
      <SheetBody>
        <dl className="grid grid-cols-[160px_minmax(0,1fr)] gap-x-3.5 gap-y-2 text-[13px]">
          <dt className="text-fg-2">{t("claim.member")}</dt>
          <dd>{c.member_display_name}</dd>
          <dt className="text-fg-2">{t("claim.provider")}</dt>
          <dd>{c.provider_name}</dd>
          <dt className="text-fg-2">{t("claim.serviceDate")}</dt>
          <dd className="tabular-nums">{formatDate(c.service_date)}</dd>
          <dt className="text-fg-2">{t("claim.covered")}</dt>
          <dd className="tabular-nums">{formatMoney(c.covered_xof)}</dd>
          {detail.patient_share_xof !== undefined ? (
            <>
              <dt className="text-fg-2">{t("claim.patientShare")}</dt>
              <dd className="tabular-nums">{formatMoney(detail.patient_share_xof)}</dd>
            </>
          ) : null}
          <dt className="text-fg-2">{t("claim.rule")}</dt>
          <dd className="tabular text-xs">
            {c.rule ? t("common.ruleWithVersion", { code: c.rule.code, version: c.rule.version }) : t("common.none")}
          </dd>
          {detail.review_due_at ? (
            <>
              <dt className="text-fg-2">{t("claim.reviewDue")}</dt>
              <dd className="tabular-nums">{formatDateTime(detail.review_due_at, timezone)}</dd>
            </>
          ) : null}
        </dl>

        <section aria-labelledby="items-title" className="flex flex-col gap-2">
          <h3 id="items-title" className="eyebrow">
            {t("claim.itemsTitle")}
          </h3>
          <div className="rounded-md border border-line">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("claim.itemAct")}</TableHead>
                  <TableHead className="text-right">{t("claim.itemQty")}</TableHead>
                  <TableHead className="text-right">{t("claim.itemAmount")}</TableHead>
                  <TableHead className="text-right">{t("claim.itemCovered")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {detail.items.map((item) => (
                  <TableRow key={item.line_no}>
                    <TableCell>{item.label}</TableCell>
                    <TableCell className="tabular text-right">{item.quantity}</TableCell>
                    <TableCell className="tabular text-right">{formatMoney(item.amount_xof, { unit: false })}</TableCell>
                    <TableCell className="tabular text-right">{formatMoney(item.covered_xof, { unit: false })}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>

        <MedicalReasonPanel claimId={c.id} />

        <section aria-labelledby="decisions-title" className="flex flex-col gap-2">
          <h3 id="decisions-title" className="eyebrow">
            {t("claim.decisionsTitle")}
          </h3>
          <ol aria-labelledby="decisions-title" className="flex flex-col gap-1.5">
            {detail.decisions.map((d) => (
              <li key={d.sequence} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 rounded-md bg-sunk px-3 py-2 text-[13px]">
                <span className="font-medium">{tDynamic("claim.decisionOutcome", d.outcome)}</span>
                <span className="text-fg-2">
                  {d.source === "regle" ? t("claim.decisionSourceRule") : t("claim.decisionSourceHuman")}
                </span>
                <span className="tabular text-xs text-fg-2">
                  {d.rule ? t("common.ruleWithVersion", { code: d.rule.code, version: d.rule.version }) : d.reason_code}
                </span>
                <span className="tabular ml-auto text-xs text-fg-2">{formatDateTime(d.decided_at, timezone)}</span>
              </li>
            ))}
          </ol>
        </section>

        {detail.authorization ? (
          <p className="text-[13px]">
            <span className="eyebrow mr-2">{t("claim.authorizationTitle")}</span>
            <span className="tabular">
              {t("claim.authorizationValue", {
                number: detail.authorization.authorization_number,
                amount: formatMoney(detail.authorization.covered_xof),
              })}
            </span>
          </p>
        ) : null}

        {canDecide ? <DecisionActions claim={c} /> : null}
        {!has("medecin_conseil") && c.status === "en_revue" ? (
          <p className="text-xs text-fg-2">{t("decision.reservedToDoctor")}</p>
        ) : null}
      </SheetBody>
    </>
  );
}
