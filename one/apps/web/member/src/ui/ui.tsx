"use client";

import { forwardRef, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { t } from "@/i18n";
import { formatXofParts } from "@/lib/format";
import { TONE_CLASS, type StatusIcon, type StatusLook, type StatusTone } from "./tones";

/* ---------------------------------------------------------------------------------------------
 * Icônes : tracés de la planche « Registre émeraude » (specs/design/direction/index.html),
 * trait 1,75 px, couleur héritée du texte. Toujours décoratives (aria-hidden) : le sens est
 * porté par le mot qui les accompagne.
 * ------------------------------------------------------------------------------------------- */
const ICONS = {
  check: <path d="M5 12.5l4.2 4.2L19 7" />,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  minus: <path d="M6 12h12" />,
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
  lock: (
    <>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    </>
  ),
  card: (
    <>
      <rect x="3" y="5.5" width="18" height="13" rx="2.5" />
      <path d="M3 10h18M7 15h4" />
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
  clip: (
    <>
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
      <rect x="9" y="3" width="6" height="4" rx="1" />
      <path d="m9 14 2 2 4-4" />
    </>
  ),
  wallet: (
    <>
      <path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H18v3" />
      <rect x="4" y="8" width="16" height="11" rx="2.5" />
      <path d="M15.5 13.5h1" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <path d="M16 4.5a3.5 3.5 0 0 1 0 7M21 20c0-2.6-1.6-4.9-4-5.7" />
    </>
  ),
  phone: (
    <>
      <rect x="7" y="3" width="10" height="18" rx="2.5" />
      <path d="M11 17.5h2" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.4 2.6 3.5 5.4 3.5 8.5s-1.1 5.9-3.5 8.5c-2.4-2.6-3.5-5.4-3.5-8.5s1.1-5.9 3.5-8.5z" />
    </>
  ),
  shield: (
    <>
      <path d="M12 3.5 19 6v5.5c0 4.4-3 7.6-7 9-4-1.4-7-4.6-7-9V6z" />
      <path d="m9 12 2 2 4-4" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 11a8 8 0 1 0-2.3 5.7" />
      <path d="M20 5v6h-6" />
    </>
  ),
  wifiOff: (
    <>
      <path d="M3 3l18 18" />
      <path d="M8.5 16a5 5 0 0 1 7 0M5 12.5a10 10 0 0 1 4-2.4M19 12.5a10 10 0 0 0-3.2-2.2M2 9a15 15 0 0 1 5-2.9M22 9a15 15 0 0 0-9.5-3.4M12 19.5v.1" />
    </>
  ),
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  signOut: (
    <>
      <path d="M13.5 4.5h-6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h6" />
      <path d="M10 12h10M16.5 8.5 20 12l-3.5 3.5" />
    </>
  ),
  back: <path d="M19 12H5M11 6l-6 6 6 6" />,
  bell: (
    <>
      <path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15z" />
      <path d="M10 20.5a2 2 0 0 0 4 0" />
    </>
  ),
  chev: <path d="m9 6 6 6-6 6" />,
  share: (
    <>
      <circle cx="17.5" cy="5.5" r="2.5" />
      <circle cx="6.5" cy="12" r="2.5" />
      <circle cx="17.5" cy="18.5" r="2.5" />
      <path d="m8.7 10.8 6.6-4M8.7 13.2l6.6 4" />
    </>
  ),
  message: (
    <>
      <path d="M4.5 19.5 6 15.6A7.5 7.5 0 1 1 9 18.6z" />
      <path d="M9 11h6M9 14h4" />
    </>
  ),
  copy: (
    <>
      <rect x="8.5" y="8.5" width="11" height="11" rx="2" />
      <path d="M15.5 8.5V6.5a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2" />
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

export function Icon({ name, className = "" }: { name: IconName | StatusIcon; className?: string }) {
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

/** Guilloche : rosette d'ellipses de la carte du site (décor, couleur héritée, très atténuée en CSS). */
export function Guilloche({ className = "guil" }: { className?: string }) {
  return (
    <svg viewBox="-100 -100 200 200" aria-hidden="true" focusable="false" className={className}>
      <g fill="none" stroke="currentColor" strokeWidth="0.7">
        {Array.from({ length: 12 }, (_, i) => (
          <ellipse key={i} rx="92" ry="30" transform={`rotate(${i * 15})`} />
        ))}
        <circle r="96" />
        <circle r="64" />
        <circle r="34" />
      </g>
    </svg>
  );
}

/** Pouls or du logo (décor de la carte). */
export function Pulse() {
  return (
    <svg viewBox="0 0 72 16" aria-hidden="true" focusable="false" className="pulse">
      <path d="M1 8h26l4-6 6 12 4-8 3 2h27" />
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
 * Boutons : 48 px minimum, 56 px pour l'action principale (une seule par écran).
 * En cours : libellé conservé, toupie à gauche, bouton désactivé.
 * ------------------------------------------------------------------------------------------- */
type Variant = "primary" | "secondary" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  busy?: boolean;
  icon?: IconName;
  trailing?: IconName;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", busy = false, icon, trailing, className = "", children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      aria-busy={busy || undefined}
      disabled={disabled || busy}
      data-variant={variant}
      className={`btn btn-${variant} ${className}`}
      {...rest}
    >
      {busy ? <Spinner /> : null}
      {!busy && icon ? <Icon name={icon} /> : null}
      <span>{children}</span>
      {trailing && !busy ? <Icon name={trailing} /> : null}
    </button>
  );
});

/* ---------------------------------------------------------------------------------------------
 * Statuts : tons sémantiques seulement, jamais l'accent. Icône + mot.
 * ------------------------------------------------------------------------------------------- */
const TONE_ICON: Record<StatusTone, StatusIcon> = { ok: "check", warn: "alert", crit: "alert", info: "info", neutral: "minus" };

interface NoticeProps {
  tone: StatusTone;
  role?: "status" | "alert";
  title?: ReactNode;
  children?: ReactNode;
  testId?: string;
  icon?: IconName | StatusIcon;
  /** Code stable (`PAY-03`, `E-NET-02`) affiché sous le message. */
  code?: string;
  className?: string;
}

export function Notice({ tone, role = "status", title, children, testId, icon, code, className = "" }: NoticeProps) {
  return (
    <div role={role} data-testid={testId} className={`alert ${TONE_CLASS[tone]} ${className}`}>
      <Icon name={icon ?? TONE_ICON[tone]} />
      <div className="alert-body">
        {title ? <b>{title}</b> : null}
        {children}
        {code ? (
          <span className="code-chip id" data-testid="error-code">
            {t("error.codeLabel", { code })}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function Pill({ look, label, testId }: { look: StatusLook; label?: string; testId?: string }) {
  return (
    <span className={`pill ${TONE_CLASS[look.tone]}`} data-testid={testId} data-tone={look.tone}>
      <Icon name={look.icon} />
      {label ?? t(look.label)}
    </span>
  );
}

/** Montant : chiffres tabulaires Inter, unité plus petite. Même texte que `formatXof`. */
export function Money({ amount, className = "", unit }: { amount: number; className?: string; unit?: string }) {
  const { before, number, after } = formatXofParts(amount);
  return (
    <span className={`amount ${className}`}>
      {before}
      {number}
      <span className="unit">{unit ?? after}</span>
    </span>
  );
}

/** Titre d'écran : reçoit le focus après une navigation pour que les lecteurs d'écran l'annoncent. */
export function ScreenTitle({ children, id, className = "" }: { children: ReactNode; id?: string; className?: string }) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (document.activeElement === document.body || document.activeElement === null) return;
    ref.current?.focus({ preventScroll: true });
  }, []);
  return (
    <h1 ref={ref} id={id} tabIndex={-1} className={`m-h1 ${className}`}>
      {children}
    </h1>
  );
}

/** Squelette de chargement : décor, annoncé par le texte `sr-only` du conteneur. */
export function Skeleton({ width = "100%", height }: { width?: string; height?: string }) {
  return <span aria-hidden="true" className="sk" style={{ width, ...(height ? { height } : {}) }} />;
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
