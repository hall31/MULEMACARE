"use client";

import { RadioGroup as RadioGroupPrimitive, Tabs as TabsPrimitive, Toggle as TogglePrimitive, ToggleGroup as ToggleGroupPrimitive } from "radix-ui";
import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

/* ------------------------------------------------------------------ Skeleton */
export function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return <div data-slot="skeleton" aria-hidden className={cn("rounded-md bg-sunk", className)} {...props} />;
}

/* ------------------------------------------------------------------ Toggle (filtres) */
export function Toggle({ className, ...props }: ComponentProps<typeof TogglePrimitive.Root>) {
  return (
    <TogglePrimitive.Root
      data-slot="toggle"
      className={cn(
        "rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-fg-2 hover:text-fg data-[state=on]:border-fg data-[state=on]:bg-fg data-[state=on]:text-bg",
        className,
      )}
      {...props}
    />
  );
}

/* ------------------------------------------------------------------ ToggleGroup (apparence) */
export function ToggleGroup({ className, ...props }: ComponentProps<typeof ToggleGroupPrimitive.Root>) {
  return (
    <ToggleGroupPrimitive.Root
      data-slot="toggle-group"
      className={cn("inline-flex gap-0.5 rounded-full border border-line bg-sunk p-[3px]", className)}
      {...props}
    />
  );
}

export function ToggleGroupItem({ className, ...props }: ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      className={cn(
        "inline-flex min-h-7 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium text-fg-2 hover:text-fg data-[state=on]:bg-surface data-[state=on]:text-fg data-[state=on]:shadow-sm [&_svg]:size-3.5",
        className,
      )}
      {...props}
    />
  );
}

/* ------------------------------------------------------------------ Tabs */
export const Tabs = (props: ComponentProps<typeof TabsPrimitive.Root>) => (
  <TabsPrimitive.Root data-slot="tabs" className="flex flex-col gap-4" {...props} />
);

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn("flex gap-1 overflow-x-auto border-b border-line", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      className={cn(
        "-mb-px border-b-2 border-transparent px-2.5 py-2 font-medium whitespace-nowrap text-fg-2 hover:text-fg data-[state=active]:border-brand data-[state=active]:text-fg",
        className,
      )}
      {...props}
    />
  );
}

export const TabsContent = ({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) => (
  <TabsPrimitive.Content data-slot="tabs-content" className={cn("flex flex-col gap-4", className)} {...props} />
);

/* ------------------------------------------------------------------ RadioGroup */
export function RadioGroup({ className, ...props }: ComponentProps<typeof RadioGroupPrimitive.Root>) {
  return <RadioGroupPrimitive.Root data-slot="radio-group" className={cn("flex flex-col gap-2", className)} {...props} />;
}

export function RadioGroupItem({ className, ...props }: ComponentProps<typeof RadioGroupPrimitive.Item>) {
  return (
    <RadioGroupPrimitive.Item
      data-slot="radio-group-item"
      className={cn(
        "grid size-4 shrink-0 place-items-center rounded-full border border-line-2 bg-surface data-[state=checked]:border-brand",
        className,
      )}
      {...props}
    >
      <RadioGroupPrimitive.Indicator className="size-2 rounded-full bg-brand" />
    </RadioGroupPrimitive.Item>
  );
}

/* ------------------------------------------------------------------ Input et NativeSelect */
export function Input({ className, ...props }: ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      className={cn(
        "h-[34px] w-full rounded-md border border-line-2 bg-surface px-3 text-[13px] text-fg placeholder:text-fg-2",
        className,
      )}
      {...props}
    />
  );
}

export function NativeSelect({ className, ...props }: ComponentProps<"select">) {
  return (
    <select
      data-slot="native-select"
      className={cn("h-[34px] w-full rounded-md border border-line bg-surface px-2.5 text-[13px] text-fg", className)}
      {...props}
    />
  );
}
