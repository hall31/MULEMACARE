"use client";

import { AlertTriangleIcon, InboxIcon, LockIcon, RotateCcwIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { ApiError } from "@/api/client";
import { t } from "@/i18n";
import { cn } from "@/lib/cn";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/misc";

/**
 * État vide guidé : dit ce qui manque, sans chiffre inventé, puis « que faire ensuite » (une
 * phrase et, s'il existe, le geste qui débloque : effacer un filtre, ouvrir la recherche).
 */
export function EmptyState({
  title,
  body,
  next,
  action,
  className,
}: {
  title: string;
  body?: string;
  next?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-2 px-6 py-10 text-center", className)} data-testid="empty-state">
      <InboxIcon className="size-6 text-fg-2" aria-hidden />
      <p className="font-display font-semibold">{title}</p>
      {body ? <p className="max-w-[48ch] text-fg-2">{body}</p> : null}
      {next ? (
        <div className="mt-1 flex max-w-[52ch] flex-col items-center gap-1" data-testid="empty-next">
          <p className="text-caption font-semibold text-fg">{t("emptyNext.title")}</p>
          <p>{next}</p>
        </div>
      ) : null}
      {action ? <div className="mt-2 flex flex-wrap justify-center gap-2">{action}</div> : null}
    </div>
  );
}

/** Ouvre la palette ⌘K depuis un état vide (la palette écoute cet événement). */
export const OPEN_PALETTE_EVENT = "mulema:open-palette";

export function OpenPaletteButton() {
  return (
    <Button variant="outline" size="sm" onClick={() => window.dispatchEvent(new Event(OPEN_PALETTE_EVENT))}>
      {t("emptyNext.openPalette")}
    </Button>
  );
}

/**
 * État d'erreur : affiche le `message` et l'`action` du Problem renvoyé par l'API
 * (déjà en français simple), et la référence support.
 */
export function ErrorState({
  error,
  onRetry,
  title,
  code,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  /** Code stable affiché (contrat §8), pour une erreur détectée par l'écran lui-même. */
  code?: string;
  className?: string;
}) {
  const problem = error instanceof ApiError ? error.problem : null;
  const forbidden = error instanceof ApiError && error.status === 403;
  const Icon = forbidden ? LockIcon : AlertTriangleIcon;
  return (
    <div role="alert" className={cn("flex flex-col items-start gap-2 rounded-md border border-line bg-surface p-4", className)}>
      <div className="flex items-center gap-2">
        <Icon className={cn("size-4", forbidden ? "text-fg-2" : "text-crit")} aria-hidden />
        <p className="font-semibold">{title ?? (forbidden ? t("states.forbiddenTitle") : t("states.errorTitle"))}</p>
      </div>
      <p>{problem?.message ?? t("states.unknownError")}</p>
      <p className="text-fg-2">{problem?.action ?? t("states.unknownAction")}</p>
      {code ? <p className="tabular text-caption text-fg-2">{code}</p> : null}
      {problem?.request_id ? (
        <p className="tabular text-xs text-fg-2">{t("states.errorRequestId", { id: problem.request_id })}</p>
      ) : null}
      {onRetry && !forbidden ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCcwIcon aria-hidden />
          {t("states.retry")}
        </Button>
      ) : null}
    </div>
  );
}

/** Chargement : lignes squelettes annoncées une seule fois aux lecteurs d'écran. */
export function LoadingRows({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-2 p-4", className)} role="status" aria-live="polite">
      <span className="sr-only">{t("states.loading")}</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

export function Panel({ className, children, ...props }: { className?: string; children: ReactNode } & ComponentProps<"section">) {
  return (
    <section className={cn("rounded-lg border border-line bg-surface", className)} {...props}>
      {children}
    </section>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
      <h1 className="text-[26px] font-semibold">{title}</h1>
      {children}
    </div>
  );
}
