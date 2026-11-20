import { describe, expect, it } from "vitest";
import { formatDate, formatDateTime, formatMoney, formatScore, formatBasisPoints } from "../../src/lib/format";

// Espaces insécables produites par Intl en fr-FR.
const norm = (s: string) => s.replace(/[  ]/g, " ");

describe("formatage", () => {
  it("montants FCFA entiers, sans décimales", () => {
    expect(norm(formatMoney(185000))).toBe("185 000 FCFA");
    expect(norm(formatMoney(0))).toBe("0 FCFA");
    expect(norm(formatMoney(4812300, { unit: false }))).toBe("4 812 300");
  });

  it("refuse un montant non entier (argent en entiers, AGENTS.md)", () => {
    expect(() => formatMoney(12.5)).toThrow();
  });

  it("dates affichées dans le fuseau de l'organisation", () => {
    // 23:30 UTC le 30/09 → 23:30 à Abidjan (UTC+0), toujours le 30/09.
    expect(norm(formatDateTime("2026-09-30T23:30:00Z", "Africa/Abidjan"))).toBe("30/09/2026 23:30");
    expect(norm(formatDate("2026-01-01"))).toBe("01/01/2026");
  });

  it("score et taux en notation française", () => {
    expect(formatScore(0.06)).toBe("0,06");
    expect(formatBasisPoints(8000)).toBe("80");
    expect(formatBasisPoints(7550)).toBe("75,5");
  });
});
