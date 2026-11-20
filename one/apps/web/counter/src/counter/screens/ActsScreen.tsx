"use client";

import type { TariffItem } from "@/api/types";
import { t } from "@/i18n";
import { formatXofParts } from "@/lib/format";
import { Button, Icon, Money, ScreenTitle, Seal, Skeleton, useDelayed } from "../ui";
import { ScreenLayout } from "./ScreenLayout";

interface Props {
  tariff: TariffItem[];
  selected: readonly string[];
  busy: boolean;
  /** Barème en cours de chargement (premier passage en ligne). */
  loading?: boolean;
  /** Relance le chargement du barème ; absent hors ligne. */
  onRetryTariff?: () => void;
  onToggle: (actCode: string) => void;
  onSubmit: () => void;
}

const SKELETON_ROWS = ["72%", "48%", "60%"];

export function ActsScreen({ tariff, selected, busy, loading = false, onRetryTariff, onToggle, onSubmit }: Props) {
  const total = tariff.filter((item) => selected.includes(item.act_code)).reduce((sum, item) => sum + item.amount_xof, 0);
  const waiting = loading && tariff.length === 0;
  const showSkeleton = useDelayed(waiting);
  return (
    <ScreenLayout
      footer={
        <Button onClick={onSubmit} busy={busy} disabled={busy || tariff.length === 0} trailing="arrow">
          {t("acts.submit")}
        </Button>
      }
    >
      <ScreenTitle>{t("acts.title")}</ScreenTitle>
      {waiting ? (
        <div className="panel acts-list" role="status" data-testid="acts-loading">
          <span className="sr-only">{t("acts.loading")}</span>
          {showSkeleton
            ? SKELETON_ROWS.map((width) => (
                <div key={width} className="sk-row" aria-hidden="true">
                  <Skeleton width="28px" />
                  <Skeleton width={width} />
                </div>
              ))
            : null}
        </div>
      ) : tariff.length === 0 ? (
        <div className="empty" role="status" data-testid="acts-empty">
          <Seal kind="empty" />
          <b>{t("acts.emptyTitle")}</b>
          <p>{t("acts.empty")}</p>
          {onRetryTariff ? (
            <Button variant="secondary" onClick={onRetryTariff} className="mt-2">
              <span className="inline-flex items-center gap-2">
                <Icon name="refresh" />
                {t("acts.retry")}
              </span>
            </Button>
          ) : null}
        </div>
      ) : (
        <fieldset className="panel acts-list">
          <legend className="sr-only">{t("acts.group")}</legend>
          {tariff.map((item) => {
            const id = `act-${item.act_code}`;
            return (
              <label key={item.act_code} htmlFor={id} className="act">
                <input id={id} type="checkbox" checked={selected.includes(item.act_code)} onChange={() => onToggle(item.act_code)} data-act={item.act_code} />
                <span aria-hidden="true" className="act-box">
                  <Icon name="check" />
                </span>
                <span className="act-label">
                  <span>{item.label}</span>
                  {item.requires_prior_approval ? <span className="font-semibold text-warn">{t("acts.priorApproval")}</span> : null}
                </span>
                <span className="act-amount amount">{formatXofParts(item.amount_xof).number}</span>
              </label>
            );
          })}
        </fieldset>
      )}
      <div className="pay-hero" aria-live="polite">
        <span className="pay-hero-label">{t("acts.total")}</span>
        <Money amount={total} className="money-display" />
      </div>
    </ScreenLayout>
  );
}
