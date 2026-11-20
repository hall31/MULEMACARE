/** Composition de classes (sans dépendance : les classes ne se recouvrent pas dans cette app). */
export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
