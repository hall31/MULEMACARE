import { ShieldAlertIcon } from "lucide-react";
import type { ComponentProps } from "react";
import type { ClaimStatus, Contribution, MemberStatus, PlanVersionState } from "@/api/types";
import { t, tDynamic } from "@/i18n";
import {
  CLAIM_STATUS_TONE,
  CONTRIBUTION_STATUS_TONE,
  MEMBER_STATUS_TONE,
  PLAN_VERSION_TONE,
  TONE_CLASSES,
  riskTone,
} from "@/lib/status";
import { formatScore } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Badge } from "./ui/badge";

export function ClaimStatusBadge({ status, ...props }: { status: ClaimStatus } & ComponentProps<"span">) {
  return (
    <Badge tone={CLAIM_STATUS_TONE[status]} {...props}>
      {tDynamic("claimStatus", status)}
    </Badge>
  );
}

export function FraudBadge() {
  return (
    <Badge tone="crit" dot={false}>
      <ShieldAlertIcon className="size-3.5" aria-hidden />
      {t("fraud.flagged")}
    </Badge>
  );
}

export function MemberStatusBadge({ status }: { status: MemberStatus }) {
  return <Badge tone={MEMBER_STATUS_TONE[status]}>{tDynamic("memberStatus", status)}</Badge>;
}

export function ContributionStatusBadge({ status }: { status: Contribution["status"] }) {
  return <Badge tone={CONTRIBUTION_STATUS_TONE[status]}>{tDynamic("contributionStatus", status)}</Badge>;
}

export function PlanVersionBadge({ state }: { state: PlanVersionState }) {
  return <Badge tone={PLAN_VERSION_TONE[state]}>{tDynamic("planVersionState", state)}</Badge>;
}

const BAR_FILL: Record<string, string> = {
  ok: "bg-ok",
  warn: "bg-warn",
  crit: "bg-crit",
  neutral: "bg-fg-2",
};

/** Barre de progression sémantique (risque, plafond). Le texte porte l'information, la couleur l'appuie. */
export function Meter({ ratio, tone, width = "w-16", label }: { ratio: number; tone: keyof typeof TONE_CLASSES; width?: string; label: string }) {
  const pct = Math.max(4, Math.min(100, Math.round(ratio * 100)));
  return (
    <span
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(ratio * 100)}
      className={cn("inline-block h-1.5 overflow-hidden rounded-full bg-sunk", width)}
    >
      <span className={cn("block h-full rounded-full", BAR_FILL[tone])} style={{ width: `${pct}%` }} />
    </span>
  );
}

export function RiskCell({ score }: { score: number | null | undefined }) {
  if (score === null || score === undefined) return <span className="text-fg-2">{t("common.none")}</span>;
  const label = t("claims.riskValue", { score: formatScore(score) });
  return (
    <span className="inline-flex items-center gap-2">
      <Meter ratio={score} tone={riskTone(score)} label={label} />
      <span className="tabular text-xs text-fg-2" aria-hidden>
        {formatScore(score)}
      </span>
    </span>
  );
}
