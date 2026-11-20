"use client";

import { AlertDialog as AlertDialogPrimitive } from "radix-ui";
import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";
import { buttonVariants } from "./button";

/** Confirmation (shadcn/ui AlertDialog) : utilisée avant toute décision sur un dossier. */
export const AlertDialog = (props: ComponentProps<typeof AlertDialogPrimitive.Root>) => (
  <AlertDialogPrimitive.Root data-slot="alert-dialog" {...props} />
);

export function AlertDialogContent({ className, ...props }: ComponentProps<typeof AlertDialogPrimitive.Content>) {
  return (
    <AlertDialogPrimitive.Portal>
      <AlertDialogPrimitive.Overlay className="scrim fixed inset-0 z-[60]" />
      <AlertDialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          "fixed top-1/2 left-1/2 z-[61] flex w-[min(480px,calc(100%-32px))] -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-lg border border-line bg-surface p-5 shadow-overlay",
          className,
        )}
        {...props}
      />
    </AlertDialogPrimitive.Portal>
  );
}

export const AlertDialogTitle = ({ className, ...props }: ComponentProps<typeof AlertDialogPrimitive.Title>) => (
  <AlertDialogPrimitive.Title className={cn("font-display text-[17px] font-semibold", className)} {...props} />
);

export const AlertDialogDescription = ({ className, ...props }: ComponentProps<typeof AlertDialogPrimitive.Description>) => (
  <AlertDialogPrimitive.Description className={cn("text-fg-2", className)} {...props} />
);

export function AlertDialogFooter({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("flex flex-wrap justify-end gap-2", className)} {...props} />;
}

export const AlertDialogCancel = ({ className, ...props }: ComponentProps<typeof AlertDialogPrimitive.Cancel>) => (
  <AlertDialogPrimitive.Cancel className={cn(buttonVariants({ variant: "outline" }), className)} {...props} />
);
