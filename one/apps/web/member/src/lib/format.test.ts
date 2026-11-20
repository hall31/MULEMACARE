import { describe, expect, it } from "vitest";
import {
  eurEquivalentCents,
  formatDate,
  formatDateOnly,
  formatDayMonth,
  formatEurCents,
  formatMonthYear,
  formatRateBp,
  formatTime,
  formatXof,
  formatXofParts,
  usedPercent,
  withDe,
} from "./format";

const NNBSP = " ";
const NBSP = " ";

describe("montants en entiers FCFA", () => {
  it("espace fine insécable entre milliers, insécable avant l'unité", () => {
    expect(formatXof(2_580_000)).toBe(`2${NNBSP}580${NNBSP}000${NBSP}FCFA`);
    expect(formatXof(0)).toBe(`0${NBSP}FCFA`);
  });

  it("refuse un montant non entier : jamais de flottant", () => {
    expect(() => formatXof(27_500.5)).toThrow();
  });

  it("le découpage pour le montant héros redonne le même texte", () => {
    const { before, number, after } = formatXofParts(27_500);
    expect(before + number + after).toBe(formatXof(27_500));
  });

  it("taux en points de base", () => {
    expect(formatRateBp(8000)).toBe(`80${NBSP}%`);
  });
});

describe("plafond familial", () => {
  it("part utilisée en pour cent entiers, bornée", () => {
    expect(usedPercent(420_000, 3_000_000)).toBe(14);
    expect(usedPercent(0, 3_000_000)).toBe(0);
    expect(usedPercent(3_500_000, 3_000_000)).toBe(100);
    expect(usedPercent(1, 3_000_000)).toBe(1);
    expect(usedPercent(10, 0)).toBe(0);
  });
});

describe("équivalent en euros (parité fixe 1 € = 655,957 FCFA)", () => {
  it("calcul entier en centimes, arrondi au centime le plus proche", () => {
    expect(eurEquivalentCents(27_500)).toBe(4_192);
    expect(eurEquivalentCents(655_957)).toBe(100_000);
    expect(eurEquivalentCents(0)).toBe(0);
  });

  it("affichage français", () => {
    expect(formatEurCents(4_192)).toBe(`41,92${NBSP}€`);
    expect(formatEurCents(123_456_7)).toBe(`12${NNBSP}345,67${NBSP}€`);
    expect(formatEurCents(5)).toBe(`0,05${NBSP}€`);
  });
});

describe("dates : UTC en base, heure locale de l'instance à l'affichage", () => {
  it("instant affiché dans le fuseau de l'instance", () => {
    expect(formatDayMonth("2026-09-28T23:30:00Z", "Africa/Abidjan")).toBe("28/09");
    expect(formatTime("2026-09-28T14:51:00Z", "Africa/Dakar")).toBe("14:51");
    expect(formatDate("2026-10-08T00:00:00Z", "Africa/Abidjan")).toBe("08/10/2026");
  });

  it("date sans heure : jamais décalée par le fuseau du navigateur", () => {
    expect(formatDateOnly("2026-10-05")).toBe("05/10/2026");
    expect(formatMonthYear("2026-10-01")).toBe("octobre 2026");
  });
});

describe("élision de « de » devant une voyelle", () => {
  it("d'octobre, d'août, d'avril ; de septembre, de mars", () => {
    expect(withDe("octobre 2026")).toBe("d’octobre 2026");
    expect(withDe("août")).toBe("d’août");
    expect(withDe("avril 2027")).toBe("d’avril 2027");
    expect(withDe("septembre 2026")).toBe("de septembre 2026");
    expect(withDe("mars")).toBe("de mars");
  });
});
