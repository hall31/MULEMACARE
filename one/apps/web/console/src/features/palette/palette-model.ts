import type { SearchHit } from "@/api/types";

/**
 * Modèle de la palette ⌘K (pur, testé sans navigateur) : groupes d'options et navigation clavier.
 * Ordre : actions (brouillon de décision du dossier ouvert, question à JOE), puis résultats par type
 * (adhérents, dossiers, prestataires) ; sans texte, les questions d'exemple.
 */
export const EXAMPLE_KEYS = ["review", "unpaid", "fraud"] as const;
export type ExampleKey = (typeof EXAMPLE_KEYS)[number];

export type PaletteOption =
  | { kind: "draft"; id: string; claimId: string; number: string }
  | { kind: "ask"; id: string; question: string }
  | { kind: "example"; id: string; example: ExampleKey }
  | { kind: "hit"; id: string; hit: SearchHit };

export type GroupKey = "commands" | "examples" | SearchHit["type"];

export interface PaletteGroup {
  key: GroupKey;
  options: PaletteOption[];
}

export interface BuildInput {
  /** Texte saisi, tel quel. */
  q: string;
  hits: readonly SearchHit[];
  /** Dossier ouvert en revue, pour le médecin-conseil seulement. */
  draftFor: { claimId: string; number: string } | null;
}

export const MIN_QUERY = 2;

export function buildGroups({ q, hits, draftFor }: BuildInput): PaletteGroup[] {
  const text = q.trim();
  const commands: PaletteOption[] = [];
  if (draftFor) commands.push({ kind: "draft", id: "draft", claimId: draftFor.claimId, number: draftFor.number });
  if (text.length >= MIN_QUERY) commands.push({ kind: "ask", id: "ask", question: text });
  const groups: PaletteGroup[] = [];
  if (commands.length > 0) groups.push({ key: "commands", options: commands });
  if (text.length < MIN_QUERY) {
    groups.push({ key: "examples", options: EXAMPLE_KEYS.map((example) => ({ kind: "example", id: `example-${example}`, example })) });
    return groups;
  }
  for (const type of ["member", "claim", "provider"] as const) {
    const options = hits.filter((h) => h.type === type).map((hit): PaletteOption => ({ kind: "hit", id: `${type}-${hit.id}`, hit }));
    if (options.length > 0) groups.push({ key: type, options });
  }
  return groups;
}

export function flatten(groups: readonly PaletteGroup[]): PaletteOption[] {
  return groups.flatMap((g) => g.options);
}

/** Flèches : déplacement circulaire ; Début et Fin : premier et dernier. */
export function moveActive(index: number, key: "ArrowDown" | "ArrowUp" | "Home" | "End", count: number): number {
  if (count === 0) return -1;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  if (index < 0) return key === "ArrowDown" ? 0 : count - 1;
  return (index + (key === "ArrowDown" ? 1 : -1) + count) % count;
}

/** Raccourci d'ouverture : Ctrl+K (Windows, Linux, Android) ou ⌘K (macOS). */
export function isPaletteShortcut(event: Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey" | "altKey" | "shiftKey">): boolean {
  return (event.ctrlKey || event.metaKey) && !event.altKey && !event.shiftKey && event.key.toLowerCase() === "k";
}
