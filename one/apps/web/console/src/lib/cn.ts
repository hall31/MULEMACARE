import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

/**
 * Les tailles de texte du contrat (`text-caption` … `text-display`, POLISH_CONTRACT §4) sont des
 * tailles : sans cette déclaration, tailwind-merge les prend pour des couleurs et efface
 * `text-dense` dès qu'un `text-fg-2` suit.
 */
const twMerge = extendTailwindMerge({
  extend: { theme: { text: ["caption", "dense", "body", "title", "headline", "display"] } },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
