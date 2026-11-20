"use client";

import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from "@tanstack/react-table";
import type { KeyboardEvent } from "react";
import { cn } from "@/lib/cn";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";

export interface ColumnMeta {
  align?: "right";
  className?: string;
}

/**
 * Table de données (TanStack Table + shadcn/ui Table). Une ligne cliquable est aussi
 * atteignable au clavier (Tab puis Entrée ou Espace) avec un focus visible.
 */
export function DataTable<T>({
  data,
  columns,
  label,
  onRowOpen,
  rowLabel,
  getRowId,
}: {
  data: T[];
  columns: ColumnDef<T>[];
  label: string;
  onRowOpen?: (row: T) => void;
  rowLabel?: (row: T) => string;
  getRowId: (row: T) => string;
}) {
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel(), getRowId });

  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>, row: T) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onRowOpen?.(row);
    }
  };

  return (
    <Table aria-label={label}>
      <TableHeader>
        {table.getHeaderGroups().map((group) => (
          <TableRow key={group.id}>
            {group.headers.map((header) => {
              const meta = header.column.columnDef.meta as ColumnMeta | undefined;
              return (
                <TableHead key={header.id} className={cn(meta?.align === "right" && "text-right", meta?.className)}>
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              );
            })}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow
            key={row.id}
            tabIndex={onRowOpen ? 0 : undefined}
            aria-label={rowLabel?.(row.original)}
            onClick={onRowOpen ? () => onRowOpen(row.original) : undefined}
            onKeyDown={onRowOpen ? (e) => onKeyDown(e, row.original) : undefined}
            className={cn(onRowOpen && "cursor-pointer hover:[&>td]:bg-sunk")}
          >
            {row.getVisibleCells().map((cell) => {
              const meta = cell.column.columnDef.meta as ColumnMeta | undefined;
              return (
                <TableCell key={cell.id} className={cn(meta?.align === "right" && "tabular text-right", meta?.className)}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              );
            })}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
