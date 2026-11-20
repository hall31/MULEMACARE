import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

/** Bouton shadcn/ui, jetons MulemaCare. `default` = action principale (accent de marque). */
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-btn border text-[13px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "border-brand bg-brand text-brand-fg hover:brightness-110",
        outline: "border-line-2 bg-surface text-fg hover:bg-sunk",
        ghost: "border-transparent bg-transparent text-fg-2 hover:bg-sunk hover:text-fg",
        danger: "border-line-2 bg-surface text-crit hover:bg-crit-bg",
      },
      size: {
        default: "h-[34px] px-3",
        sm: "h-8 px-2.5 text-xs",
        icon: "size-8",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export function Button({
  className,
  variant,
  size,
  asChild = false,
  type,
  ...props
}: ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "button";
  return (
    <Comp
      data-slot="button"
      type={asChild ? undefined : (type ?? "button")}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { buttonVariants };
