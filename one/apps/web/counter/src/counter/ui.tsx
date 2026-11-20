"use client";

import { forwardRef, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { t } from "@/i18n";
import { formatXofParts } from "@/lib/format";
import { STATUS_TONE_CLASSES, type StatusTone } from "./tones";

/* ---------------------------------------------------------------------------------------------
 * Icônes : tracés de la planche « Registre émeraude » (specs/design/direction/index.html),
 * trait 1,75 px, couleur héritée du texte. Toujours décoratives (aria-hidden) : le sens est
 * porté par le mot qui les accompagne.
 * ------------------------------------------------------------------------------------------- */
const ICONS = {
  check: <path d="M5 12.5l4.2 4.2L19 7" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  alert: (
    <>
      <path d="M12 4 2.8 19.5h18.4z" />
      <path d="M12 10v4.2M12 17v.2" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  info: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5M12 8v.2" />
    </>
  ),
  qr: (
    <>
      <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
      <rect x="8" y="8" width="3" height="3" />
      <rect x="13" y="8" width="3" height="3" />
      <rect x="8" y="13" width="3" height="3" />
      <path d="M13 13h3v3" />
    </>
  ),
  pulse: <path d="M3 12h4l2-4.5 4 9 2-4.5h6" />,
  help: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.6 9.4a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.7M12 17v.2" />
    </>
  ),
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  chart: <path d="M4 20h16M7 16.5V11M12 16.5V6.5M17 16.5v-3.5" />,
  chev: <path d="m6 9 6 6 6-6" />,
  shield: (
    <>
      <path d="M12 3.5 19 6v5.5c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  wifiOff: (
    <>
      <path d="M3 3l18 18" />
      <path d="M8.5 16a5 5 0 0 1 7 0M5 12.5a10 10 0 0 1 4-2.4M19 12.5a10 10 0 0 0-3.2-2.2M2 9a15 15 0 0 1 5-2.9M22 9a15 15 0 0 0-9.5-3.4M12 19.5v.1" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 11a8 8 0 1 0-2.3 5.7" />
      <path d="M20 5v6h-6" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
    </>
  ),
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" className={`ic ${className}`}>
      {ICONS[name]}
    </svg>
  );
}

/** Marque : croix sur émeraude profond, pouls or du logo. */
export function BrandMark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" focusable="false" className="bm">
      <rect className="bm-bg" width="32" height="32" rx="9" />
      <rect className="bm-x" x="13" y="6" width="6" height="20" rx="3" />
      <rect className="bm-x" x="6" y="13" width="20" height="6" rx="3" />
      <path className="bm-p" d="M6.5 16h5l2-3.5 3 7 2-3.5h7" />
    </svg>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Cachet : double cercle qui marque toute décision. `animate` joue l'unique animation signature
 * de l'écran (400 ms, une fois, rien en mouvement réduit : voir globals.css).
 * ------------------------------------------------------------------------------------------- */
export type SealKind = "ok" | "crit" | "review" | "empty";

const SEAL_MARK: Record<SealKind, ReactNode> = {
  ok: <path d="m16.5 24.5 5 5 10-10.5" />,
  crit: <path d="m18.5 18.5 11 11M29.5 18.5l-11 11" />,
  review: <path d="M24 16.5V24l5 3" />,
  empty: null,
};

export function Seal({ kind, animate = false }: { kind: SealKind; animate?: boolean }) {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false" className={`seal${animate ? " stamp" : ""}`} data-seal={kind}>
      <circle cx="24" cy="24" r="21" />
      <circle cx="24" cy="24" r="15.5" strokeDasharray="2 3.2" />
      {SEAL_MARK[kind]}
    </svg>
  );
}

function Spinner() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" className="spinner">
      <circle cx="12" cy="12" r="9" strokeDasharray="40 100" />
    </svg>
  );
}

/* ---------------------------------------------------------------------------------------------
 * Boutons du comptoir : 48 px minimum, 56 px et pleine largeur pour l'action principale.
 * En cours : libellé conservé, toupie à gauche, bouton désactivé.
 * ------------------------------------------------------------------------------------------- */
type Variant = "primary" | "secondary" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  busy?: boolean;
  /** Icône après le libellé (flèche de l'action principale). */
  trailing?: IconName;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", busy = false, trailing, className = "", children, ...rest },
  ref,
) {
  return (
    <button ref={ref} type="button" aria-busy={busy || undefined} data-variant={variant} className={`btn btn-${variant} ${className}`} {...rest}>
      {busy ? <Spinner /> : null}
      <span>{children}</span>
      {trailing && !busy ? <Icon name={trailing} /> : null}
    </button>
  );
});

/* ---------------------------------------------------------------------------------------------
 * Statuts : tons sémantiques seulement, jamais l'accent (AGENTS.md). Icône + mot.
 * ------------------------------------------------------------------------------------------- */
const TONE_ICON: Record<StatusTone, IconName> = { ok: "check", warn: "alert", crit: "alert", info: "info" };

interface NoticeProps {
  tone: StatusTone;
  role?: "status" | "alert";
  children: ReactNode;
  testId?: string;
  icon?: IconName;
  /** Code stable (`ID-03`, `R-01`) affiché sous le message. */
  code?: string;
  className?: string;
}

export function Notice({ tone, role = "status", children, testId, icon, code, className = "" }: NoticeProps) {
  return (
    <div role={role} data-testid={testId} className={`alert ${STATUS_TONE_CLASSES[tone]} ${className}`}>
      <Icon name={icon ?? TONE_ICON[tone]} />
      <div className="alert-body">
        {children}
        {code ? <span className="code-chip id">{t("error.codeLabel", { code })}</span> : null}
      </div>
    </div>
  );
}

export function Pill({ tone, icon, children }: { tone: StatusTone; icon?: IconName; children: ReactNode }) {
  return (
    <span className={`pill ${STATUS_TONE_CLASSES[tone]}`}>
      <Icon name={icon ?? TONE_ICON[tone]} />
      {children}
    </span>
  );
}

/** Titre d'écran : reçoit le focus à l'arrivée pour que les lecteurs d'écran annoncent l'étape. */
export function ScreenTitle({ children, className = "c-h1" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    ref.current?.focus({ preventScroll: false });
  }, []);
  return (
    <h1 ref={ref} tabIndex={-1} className={className}>
      {children}
    </h1>
  );
}

export type StepName = "card" | "identity" | "code" | "acts" | "decision";

/** « 3 sur 5 · Code » : numéro d'étape en Outfit, à l'accent (état d'interface, pas un statut). */
export function StepHeader({ n, name }: { n: number; name: StepName }) {
  return (
    <p className="c-step" data-testid="step">
      <span className="c-step-n">{n}</span> <span>{t("step.of", { name: t(`step.name.${name}` as const) })}</span>
    </p>
  );
}

/** Montant : chiffres tabulaires Inter, unité plus petite. Même texte que `formatXof`. */
export function Money({ amount, className = "" }: { amount: number; className?: string }) {
  const { before, number, after } = formatXofParts(amount);
  return (
    <span className={`amount ${className}`}>
      {before}
      {number}
      <span className="unit">{after}</span>
    </span>
  );
}

/** Squelette de chargement : décor, annoncé par le texte `sr-only` du conteneur. */
export function Skeleton({ width = "100%" }: { width?: string }) {
  return <span aria-hidden="true" className="sk" style={{ width }} />;
}

/** Vrai seulement si `active` dure plus de `delayMs` : pas de squelette qui clignote (contrat §8). */
export function useDelayed(active: boolean, delayMs = 300): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!active) {
      setShown(false);
      return;
    }
    const timer = window.setTimeout(() => setShown(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [active, delayMs]);
  return active && shown;
}
