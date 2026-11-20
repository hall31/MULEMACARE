"use client";

import { XIcon } from "lucide-react";
import { Dialog as SheetPrimitive } from "radix-ui";
import type { ComponentProps } from "react";
import { t } from "@/i18n";
import { cn } from "@/lib/cn";

/** Tiroir latéral (shadcn/ui Sheet), utilisé pour le dossier et la fiche adhérent. */
export const Sheet = (props: ComponentProps<typeof SheetPrimitive.Root>) => <SheetPrimitive.Root data-slot="sheet" {...props} />;

export function SheetContent({ className, children, ...props }: ComponentProps<typeof SheetPrimitive.Content>) {
  return (
    <SheetPrimitive.Portal>
      <SheetPrimitive.Overlay data-slot="sheet-overlay" className="scrim fixed inset-0 z-40" />
      <SheetPrimitive.Content
        data-slot="sheet-content"
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex w-full max-w-[560px] flex-col border-l border-line bg-surface shadow-overlay outline-none",
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close asChild>
          <button
            type="button"
            aria-label={t("common.close")}
            className="absolute top-4 right-4 inline-flex size-8 items-center justify-center rounded-btn text-fg-2 hover:bg-sunk hover:text-fg"
          >
            <XIcon className="size-4" aria-hidden />
          </button>
        </SheetPrimitive.Close>
      </SheetPrimitive.Content>
    </SheetPrimitive.Portal>
  );
}

export function SheetHeader({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="sheet-header" className={cn("border-b border-line px-5 pt-5 pb-4 pr-14", className)} {...props} />;
}

export function SheetBody({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="sheet-body" className={cn("flex flex-1 flex-col gap-5 overflow-y-auto px-5 pt-4 pb-10", className)} {...props} />;
}

export const SheetTitle = ({ className, ...props }: ComponentProps<typeof SheetPrimitive.Title>) => (
  <SheetPrimitive.Title data-slot="sheet-title" className={cn("font-display text-lg font-semibold", className)} {...props} />
);

export const SheetDescription = ({ className, ...props }: ComponentProps<typeof SheetPrimitive.Description>) => (
  <SheetPrimitive.Description data-slot="sheet-description" className={cn("text-fg-2", className)} {...props} />
);
