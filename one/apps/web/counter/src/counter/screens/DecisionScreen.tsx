"use client";

import type { ReactNode } from "react";
import type { Beneficiary, RuleCheck, RuleRef, TariffItem } from "@/api/types";
import type { QueueRecord } from "@/offline/db";
import type { OfflineRefusal } from "@/offline/policy";
import { t, tp, type MessageKey } from "@/i18n";
import { formatRateBp, formatTime, formatXof, formatXofParts, initials } from "@/lib/format";
import type { Outcome } from "../outcome";
import { Button, Icon, Money, Notice, Pill, ScreenTitle, Seal, type SealKind } from "../ui";
import { MEMBER_STATUS } from "./IdentityScreen";
import { ScreenLayout } from "./ScreenLayout";

const REFUSAL_KEY: Record<OfflineRefusal, MessageKey> = {
  above_threshold: "decision.offline.aboveThreshold",
  no_policy: "decision.offline.noPolicy",
  stale_policy: "decision.offline.stalePolicy",
  no_device: "decision.offline.noDevice",
  member_status: "decision.offline.memberStatus",
  prior_approval: "decision.offline.priorApproval",
  unknown_act: "decision.offline.unknownAct",
  not_verified: "decision.offline.notVerified",
};

interface Props {
  outcome: Outcome;
  record: QueueRecord | undefined;
  thresholdXof: number | null;
  timeZone: string;
  busy: boolean;
  /** Personne identifiée (rappel sous la décision). */
  beneficiary?: Beneficiary | undefined;
  /** Actes demandés, au barème en vigueur à la date du soin. */
  acts?: readonly TariffItem[];
  onNext: () => void;
  onRetry: () => void;
  onEditActs: () => void;
}

type VerdictTone = "ok" | "warn" | "crit";
const SEAL: Record<VerdictTone, SealKind> = { ok: "ok", warn: "review", crit: "crit" };

/** Le cachet : décision, règle versionnée. Seule animation signature de l'écran. */
function Verdict({ tone, title, rule, children }: { tone: VerdictTone; title: string; rule?: RuleRef | undefined; children?: ReactNode }) {
  return (
    <section className={`verdict verdict-${tone}`} data-testid="verdict">
      <Seal kind={SEAL[tone]} animate />
      <div className="verdict-body">
        <ScreenTitle className="verdict-title">{title}</ScreenTitle>
        {children}
        {rule ? <span className="rule id">{t("decision.rule", { code: rule.code, version: rule.version })}</span> : null}
      </div>
    </section>
  );
}

/** Montant héros : ce que le comptoir encaisse, puis la part de la mutuelle. */
function Collect({ amount, covered, rateBp }: { amount: number; covered?: number; rateBp?: number | undefined }) {
  return (
    <div className="pay-hero" data-testid="collect">
      <span className="pay-hero-label">{t("decision.collect")}</span>
      <Money amount={amount} className="money-display" />
      {covered === undefined ? null : (
        <div className="pay-mc">
          <span>{rateBp === undefined ? t("decision.mulemaPays") : t("decision.mulemaPaysRate", { rate: formatRateBp(rateBp) })}</span>
          <b className="amount">{formatXof(covered)}</b>
        </div>
      )}
    </div>
  );
}

function Who({ beneficiary, reference }: { beneficiary: Beneficiary | undefined; reference: string }) {
  const status = beneficiary ? MEMBER_STATUS[beneficiary.member_status] : null;
  return (
    <div className="who-row">
      {beneficiary ? (
        <span className="av av-md" aria-hidden="true">
          {initials(beneficiary.display_name)}
        </span>
      ) : null}
      <div>
        {beneficiary ? <b>{beneficiary.display_name}</b> : null}
        {beneficiary ? <span className="id">{beneficiary.member_number}</span> : null}
        <span className="id">{t("decision.reference", { ref: reference })}</span>
        {beneficiary && status ? (
          <span className="mt-1">
            <Pill tone={status.tone} icon={status.icon}>
              {t(`identity.status.${beneficiary.member_status}` as const)}
            </Pill>
          </span>
        ) : null}
      </div>
    </div>
  );
}

function ActsPanel({ acts }: { acts: readonly TariffItem[] }) {
  if (acts.length === 0) return null;
  const total = acts.reduce((sum, item) => sum + item.amount_xof, 0);
  return (
    <section className="panel" aria-labelledby="decision-acts">
      <div className="panel-h">
        <h2 className="panel-t" id="decision-acts">
          {t("decision.acts")}
        </h2>
        <span>{tp("decision.actsCount", acts.length)}</span>
      </div>
      <ul className="lines">
        {acts.map((item) => (
          <li key={item.act_code}>
            <span>{item.label}</span>
            <span className="amount">{formatXofParts(item.amount_xof).number}</span>
          </li>
        ))}
        <li className="total">
          <span>{t("decision.total")}</span>
          <span className="amount">{formatXof(total)}</span>
        </li>
      </ul>
    </section>
  );
}

function ChecksPanel({ checks }: { checks: readonly RuleCheck[] }) {
  if (checks.length === 0) return null;
  const allPassed = checks.every((c) => c.passed);
  return (
    <details className="panel checks-d">
      <summary>
        <Icon name="shield" className={allPassed ? "text-ok" : "text-crit"} />
        {tp("decision.checks", checks.length)}
        <Icon name="chev" className="chev" />
      </summary>
      <ul className="checks">
        {checks.map((check) => (
          <li key={`${check.rule.code}-${check.rule.version}`}>
            <span className={check.passed ? "ok" : "crit"}>
              <Icon name={check.passed ? "check" : "x"} />
              <span className="sr-only">{t(check.passed ? "decision.checkPassed" : "decision.checkFailed")}</span>
            </span>
            <span>{check.message}</span>
            <span className="id">{t("decision.ruleShort", { code: check.rule.code, version: check.rule.version })}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function DecisionScreen({ outcome, record, thresholdXof, timeZone, busy, beneficiary, acts = [], onNext, onRetry, onEditActs }: Props) {
  let main: ReactNode;
  let side: ReactNode = <ActsPanel acts={acts} />;
  let footer: ReactNode = (
    <Button onClick={onNext} trailing="arrow">
      {t("decision.next")}
    </Button>
  );
  const rate = beneficiary?.coverage_rate_bp;

  if (outcome.kind === "online") {
    const { decision, claim, authorization } = outcome.created;
    const reference = authorization?.authorization_number ?? claim.claim_number;
    side = (
      <>
        <ActsPanel acts={acts} />
        <ChecksPanel checks={decision.checks} />
      </>
    );
    if (decision.outcome === "accordee_auto") {
      main = (
        <>
          <Verdict tone="ok" title={t("decision.title.auto")} rule={decision.rule}>
            <p>{decision.message}</p>
          </Verdict>
          <Collect amount={decision.patient_share_xof} covered={decision.covered_xof} rateBp={rate} />
          <Who beneficiary={beneficiary} reference={reference} />
        </>
      );
    } else if (decision.outcome === "en_revue") {
      main = (
        <>
          <Verdict tone="warn" title={t("decision.title.review")} rule={decision.rule}>
            <p>{decision.message}</p>
            {decision.review_due_at ? <p className="font-semibold">{t("decision.reviewDue", { time: formatTime(decision.review_due_at, timeZone) })}</p> : null}
          </Verdict>
          <Who beneficiary={beneficiary} reference={reference} />
        </>
      );
    } else {
      main = (
        <>
          <Verdict tone="crit" title={t("decision.title.refused")} rule={decision.rule}>
            <p role="alert">{decision.message}</p>
          </Verdict>
          <Collect amount={decision.total_xof} />
          <Who beneficiary={beneficiary} reference={reference} />
        </>
      );
    }
  } else if (outcome.kind === "provisional") {
    const status = record?.status ?? "en_attente";
    main = (
      <>
        <Verdict tone="ok" title={t("decision.title.provisional")} />
        {status === "confirmee" ? (
          <Notice tone="ok" testId="provisional-status">
            {t("decision.provisionalSynced")}
          </Notice>
        ) : status === "rejetee" ? (
          <Notice tone="crit" role="alert" testId="provisional-status">
            {t("decision.provisionalRejected", { code: record?.reason_code ?? "" })}
          </Notice>
        ) : (
          <Notice tone="warn" icon="clock" testId="provisional-status">
            {t("decision.provisionalExplain", { time: formatTime(outcome.expiresAt, timeZone) })}
          </Notice>
        )}
        <Collect amount={outcome.quote.patient_share_xof} covered={outcome.quote.covered_xof} rateBp={rate} />
        <Who beneficiary={beneficiary} reference={outcome.offlineRef.slice(0, 8).toUpperCase()} />
      </>
    );
  } else {
    const message = t(REFUSAL_KEY[outcome.reason], { threshold: thresholdXof === null ? "" : formatXof(thresholdXof) });
    main = (
      <>
        <ScreenTitle>{t("decision.title.offlineBlocked")}</ScreenTitle>
        <Notice tone="warn" role="alert" icon="wifiOff">
          {message}
        </Notice>
      </>
    );
    footer = (
      <>
        <Button onClick={onRetry} busy={busy} disabled={busy}>
          {t("decision.retry")}
        </Button>
        <Button variant="secondary" onClick={onEditActs} disabled={busy}>
          {t("decision.editActs")}
        </Button>
      </>
    );
  }

  return (
    <ScreenLayout footer={footer} wide>
      <div className="c-col">{main}</div>
      <div className="c-col">{side}</div>
    </ScreenLayout>
  );
}
