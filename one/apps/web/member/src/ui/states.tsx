"use client";

import type { ReactNode } from "react";
import { toUiError } from "@/api/errors";
import { t } from "@/i18n";
import { Button, Notice, Seal, Skeleton, useDelayed } from "./ui";

/**
 * États obligatoires (docs/POLISH_CONTRACT.md §8) : chargement (squelette après 300 ms), vide
 * (cachet en contour, pourquoi, ce qui arrivera), erreur (ce qui s'est passé, quoi faire, code
 * stable, « Réessayer »).
 */
export function ErrorState({ title, error, onRetry, retrying = false, testId = "error-state" }: { title: string; error: unknown; onRetry?: () => void; retrying?: boolean; testId?: string }) {
  const ui = toUiError(error);
  return (
    <div className="state-error" data-testid={testId} data-code={ui.code}>
      <Notice tone="crit" role="alert" title={title} code={ui.code}>
        <p>{ui.text}</p>
        <p className="detail">{ui.detail}</p>
      </Notice>
      {onRetry ? (
        <Button variant="secondary" icon="refresh" busy={retrying} onClick={onRetry} className="btn-auto">
          {t("error.retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, children, action, testId = "empty-state" }: { title: string; children: ReactNode; action?: ReactNode; testId?: string }) {
  return (
    <div className="empty" data-testid={testId}>
      <Seal kind="empty" />
      <b>{title}</b>
      <p>{children}</p>
      {action}
    </div>
  );
}

/** Squelette à la forme du contenu, montré seulement si le chargement dure plus de 300 ms. */
export function LoadingState({ label, rows = 3, testId = "loading-state" }: { label: string; rows?: number; testId?: string }) {
  const shown = useDelayed(true);
  return (
    <div className="panel loading" role="status" aria-live="polite" data-testid={testId} data-shown={shown || undefined}>
      <span className="sr-only">{label}</span>
      {shown
        ? Array.from({ length: rows }, (_, i) => (
            <div key={i} className="sk-row">
              <Skeleton width={i % 2 ? "48%" : "72%"} />
              <Skeleton width="24%" />
            </div>
          ))
        : null}
    </div>
  );
}
