import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";
import { TONE_CLASSES, type Tone } from "@/lib/status";

/** Badge shadcn/ui ; le ton est toujours sémantique (ok / warn / crit / neutre). */
export function Badge({ tone = "neutral", dot = true, className, children, ...props }: ComponentProps<"span"> & { tone?: Tone; dot?: boolean }) {
  return (
    <span
      data-slot="badge"
      data-tone={tone}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium",
        TONE_CLASSES[tone],
        className,
      )}
      {...props}
    >
      {dot ? <span aria-hidden className="size-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  );
}
