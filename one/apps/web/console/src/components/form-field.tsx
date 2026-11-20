"use client";

import { AlertTriangleIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface ControlProps {
  id: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

/**
 * Champ de formulaire accessible (contrat §8) : libellé lié, aide, et erreur SOUS le champ, liée par
 * `aria-describedby` ; `aria-invalid` posé quand une erreur existe. Le contrôle est rendu par
 * l'appelant avec les propriétés reçues (champ texte, liste, couleur…).
 */
export function FormField({
  id,
  label,
  hint,
  error,
  className,
  children,
}: {
  id: string;
  label: ReactNode;
  hint?: ReactNode;
  error?: string | null;
  className?: string;
  children: (props: ControlProps) => ReactNode;
}) {
  const hintId = hint ? `${id}-aide` : null;
  const errorId = error ? `${id}-erreur` : null;
  const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-dense font-medium text-fg">
        {label}
      </label>
      {children({ id, "aria-describedby": describedBy, ...(error ? { "aria-invalid": true as const } : {}) })}
      {error ? (
        <p id={errorId ?? undefined} className="flex items-start gap-1.5 text-dense text-crit" data-testid={`${id}-erreur`}>
          <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>{error}</span>
        </p>
      ) : null}
      {hint ? (
        <p id={hintId ?? undefined} className="text-caption text-fg-2">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

/** Classes communes des champs (console : cible de 40 px, bord de contrôle à 3:1, focus visible). */
export const INPUT_CLASS =
  "h-10 w-full rounded-md border border-line-2 bg-surface px-3 text-dense text-fg aria-[invalid=true]:border-crit";
export const TEXTAREA_CLASS = "min-h-24 w-full rounded-md border border-line-2 bg-surface px-3 py-2 text-dense text-fg aria-[invalid=true]:border-crit";
