import { describe, expect, it } from "vitest";
import type { SearchHit } from "../../src/api/types";
import { buildGroups, flatten, isPaletteShortcut, moveActive } from "../../src/features/palette/palette-model";

const hit = (type: SearchHit["type"], n: number): SearchHit => ({ type, id: `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`, label: `${type} ${n}`, meta: null });

describe("palette ⌘K : options", () => {
  it("sans texte : questions d'exemple (et le brouillon du dossier ouvert s'il existe)", () => {
    expect(buildGroups({ q: "", hits: [], draftFor: null }).map((g) => g.key)).toEqual(["examples"]);
    const withDraft = buildGroups({ q: " ", hits: [], draftFor: { claimId: "c", number: "PEC-26-09813" } });
    expect(withDraft.map((g) => g.key)).toEqual(["commands", "examples"]);
    expect(withDraft[0]!.options[0]).toMatchObject({ kind: "draft", number: "PEC-26-09813" });
  });

  it("avec texte : « Demander à JOE » d'abord, puis adhérents, dossiers, prestataires (groupes vides omis)", () => {
    const groups = buildGroups({ q: "  kon ", hits: [hit("claim", 1), hit("member", 2), hit("claim", 3)], draftFor: null });
    expect(groups.map((g) => g.key)).toEqual(["commands", "member", "claim"]);
    expect(groups[0]!.options).toEqual([{ kind: "ask", id: "ask", question: "kon" }]);
    expect(flatten(groups).map((o) => o.id)).toEqual(["ask", `member-${hit("member", 2).id}`, `claim-${hit("claim", 1).id}`, `claim-${hit("claim", 3).id}`]);
  });

  it("aucun résultat : la question à JOE reste proposée", () => {
    expect(flatten(buildGroups({ q: "zzz", hits: [], draftFor: null })).map((o) => o.kind)).toEqual(["ask"]);
  });
});

describe("palette ⌘K : clavier", () => {
  it("flèches circulaires, Début, Fin ; liste vide : aucune option active", () => {
    expect(moveActive(-1, "ArrowDown", 3)).toBe(0);
    expect(moveActive(-1, "ArrowUp", 3)).toBe(2);
    expect(moveActive(2, "ArrowDown", 3)).toBe(0);
    expect(moveActive(0, "ArrowUp", 3)).toBe(2);
    expect(moveActive(1, "Home", 3)).toBe(0);
    expect(moveActive(1, "End", 3)).toBe(2);
    expect(moveActive(0, "ArrowDown", 0)).toBe(-1);
  });

  it("Ctrl+K et ⌘K ouvrent ; Ctrl+Maj+K et K seul non", () => {
    const base = { ctrlKey: false, metaKey: false, altKey: false, shiftKey: false };
    expect(isPaletteShortcut({ ...base, key: "k", ctrlKey: true })).toBe(true);
    expect(isPaletteShortcut({ ...base, key: "K", metaKey: true })).toBe(true);
    expect(isPaletteShortcut({ ...base, key: "k", ctrlKey: true, shiftKey: true })).toBe(false);
    expect(isPaletteShortcut({ ...base, key: "k" })).toBe(false);
  });
});
