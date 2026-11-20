import type { ComponentProps } from "react";
import { cn } from "@/lib/cn";

/** Table shadcn/ui, densité console. */
export function Table({ className, ...props }: ComponentProps<"table">) {
  return (
    <div data-slot="table-container" className="relative w-full overflow-x-auto">
      <table data-slot="table" className={cn("w-full border-collapse text-[13px]", className)} {...props} />
    </div>
  );
}

export const TableHeader = ({ className, ...props }: ComponentProps<"thead">) => (
  <thead data-slot="table-header" className={cn(className)} {...props} />
);

export const TableBody = ({ className, ...props }: ComponentProps<"tbody">) => (
  <tbody data-slot="table-body" className={cn("[&_tr:last-child>td]:border-b-0", className)} {...props} />
);

export const TableRow = ({ className, ...props }: ComponentProps<"tr">) => (
  <tr data-slot="table-row" className={cn(className)} {...props} />
);

export const TableHead = ({ className, ...props }: ComponentProps<"th">) => (
  <th
    data-slot="table-head"
    className={cn(
      "border-b border-line px-3.5 py-2.5 text-left text-[11px] font-semibold tracking-[0.06em] whitespace-nowrap text-fg-2 uppercase",
      className,
    )}
    {...props}
  />
);

export const TableCell = ({ className, ...props }: ComponentProps<"td">) => (
  <td data-slot="table-cell" className={cn("border-b border-line px-3.5 py-2.5 align-middle", className)} {...props} />
);
