import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/cn";

/* ------------------------------------------------------------------ Icônes (tracé, currentColor) */
const PATHS = {
  lock: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5z",
  alert: "M12 3 2 21h20L12 3zm0 7v5m0 3v.01",
  download: "M12 4v11m0 0-4-4m4 4 4-4M5 20h14",
  check: "m5 12 5 5 9-10",
  retry: "M4 12a8 8 0 1 0 2.3-5.6M4 4v4h4",
  clock: "M12 7v5l3 2M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z",
  x: "M6 6l12 12M18 6 6 18",
  minus: "M5 12h14",
  table: "M4 5h16v14H4zM4 10h16M10 5v14",
  sun: "M12 4V2m0 20v-2m8-8h2M2 12h2m13.7-5.7 1.4-1.4M4.9 19.1l1.4-1.4m11.4 1.4-1.4-1.4M6.3 6.3 4.9 4.9M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  monitor: "M3 4h18v12H3zM8 20h8m-4-4v4",
  chart: "M4 20V4m0 16h16M8 16v-5m4 5V8m4 8v-3",
  users: "M16 19v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1m7-9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm13 9v-1a4 4 0 0 0-3-3.9M16 4.1a3 3 0 0 1 0 5.8",
} as const;
export type IconName = keyof typeof PATHS;

export function Icon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" className={cn("size-4 shrink-0 fill-none stroke-current", className)} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
      <path d={PATHS[name]} />
    </svg>
  );
}

/* ------------------------------------------------------------------ Bouton : 48 px (zone tactile) */
const BUTTON = {
  primary: "border-accent bg-accent text-accent-fg hover:bg-[var(--accent-hover)] hover:border-[var(--accent-hover)]",
  outline: "border-line-2 bg-surface text-fg hover:bg-sunk",
  ghost: "border-transparent bg-transparent text-fg hover:bg-sunk",
} as const;

export function Button({ variant = "outline", className, type, ...props }: ComponentProps<"button"> & { variant?: keyof typeof BUTTON }) {
  return (
    <button
      type={type ?? "button"}
      className={cn(
        "inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-btn border px-4 text-dense font-semibold whitespace-nowrap transition-colors duration-[var(--dur-hover)] disabled:cursor-not-allowed disabled:border-line disabled:bg-sunk disabled:text-fg-2",
        BUTTON[variant],
        className,
      )}
      {...props}
    />
  );
}

/* ------------------------------------------------------------------ Pastille de statut (icône + mot) */
export type Tone = "ok" | "warn" | "crit" | "info" | "neutral";
export const TONE_CLASSES: Record<Tone, string> = {
  ok: "bg-ok-bg text-ok",
  warn: "bg-warn-bg text-warn",
  crit: "bg-crit-bg text-crit",
  info: "bg-info-bg text-info",
  neutral: "bg-sunk text-fg-2",
};
/** Couleur pleine d'une série de graphique : sémantique, ou neutre ; jamais l'accent. */
export const TONE_FILL: Record<Tone, string> = { ok: "bg-ok", warn: "bg-warn", crit: "bg-crit", info: "bg-info", neutral: "bg-line-2" };
const TONE_ICON: Record<Tone, IconName> = { ok: "check", warn: "clock", crit: "alert", info: "clock", neutral: "minus" };

export function Badge({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <span data-tone={tone} className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-caption font-semibold whitespace-nowrap", TONE_CLASSES[tone], className)}>
      <Icon name={TONE_ICON[tone]} className="size-3.5" />
      {children}
    </span>
  );
}

export function Panel({ className, children, ...props }: ComponentProps<"section">) {
  return (
    <section className={cn("rounded-lg border border-line bg-surface", className)} {...props}>
      {children}
    </section>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div data-slot="skeleton" aria-hidden className={cn("rounded-md bg-sunk", className)} />;
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="eyebrow">{eyebrow}</span>
      <h1 className="text-headline">{title}</h1>
      {children}
    </div>
  );
}

/** Tableau qui défile horizontalement sur petit écran : région nommée, atteignable au clavier. */
export function ScrollRegion({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="region" aria-label={label} tabIndex={0} className="w-full overflow-x-auto">
      {children}
    </div>
  );
}
