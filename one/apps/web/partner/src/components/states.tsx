"use client";

import { useEffect, useState, type ReactNode } from "react";
import { ApiError } from "@/api/client";
import { t } from "@/i18n";
import { cn } from "@/lib/cn";
import { Button, Icon, Skeleton } from "./ui";

/** Squelette à la forme du contenu, affiché après 300 ms seulement (contrat §8). */
export function Loading({ rows = 4, className }: { rows?: number; className?: string }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), 300);
    return () => window.clearTimeout(timer);
  }, []);
  return (
    <div role="status" aria-live="polite" className={cn("flex flex-col gap-3 p-4", className)} data-testid="loading">
      <span className="sr-only">{t("states.loading")}</span>
      {visible ? Array.from({ length: rows }, (_, i) => <Skeleton key={i} className="h-10 w-full" />) : null}
    </div>
  );
}

/** Erreur : ce qui s'est passé, quoi faire, code stable, « Réessayer ». */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const problem = error instanceof ApiError ? error.problem : null;
  const forbidden = error instanceof ApiError && error.status === 403;
  return (
    <div role="alert" className="flex flex-col items-start gap-2 rounded-md border border-line bg-surface p-4" data-testid="error-state">
      <p className="flex items-center gap-2 font-semibold">
        <Icon name={forbidden ? "lock" : "alert"} className={forbidden ? "text-fg-2" : "text-crit"} />
        {forbidden ? t("states.forbiddenTitle") : t("states.errorTitle")}
      </p>
      <p>{problem?.message ?? t("states.unknownError")}</p>
      <p className="text-fg-2">{problem?.action ?? t("states.unknownAction")}</p>
      {problem ? <p className="num text-caption text-fg-2">{t("states.code", { code: problem.code })}</p> : null}
      {problem?.request_id ? <p className="num text-caption text-fg-2">{t("states.requestId", { id: problem.request_id })}</p> : null}
      {onRetry && !forbidden ? (
        <Button onClick={onRetry}>
          <Icon name="retry" />
          {t("states.retry")}
        </Button>
      ) : null}
    </div>
  );
}

/** Vide : cachet en contour, pourquoi c'est vide et ce qui arrivera. */
export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-8 text-center" data-testid="empty-state">
      <svg viewBox="0 0 48 48" aria-hidden="true" className="size-10 fill-none stroke-line-2" strokeWidth={1.5}>
        <circle cx="24" cy="24" r="21" />
        <circle cx="24" cy="24" r="16" />
      </svg>
      <p className="font-display font-semibold">{title}</p>
      <p className="max-w-[52ch] text-fg-2">{body}</p>
      {action}
    </div>
  );
}
