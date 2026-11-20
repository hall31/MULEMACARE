import { describe, expect, it } from "vitest";
import { categoryLabel } from "../../src/features/labels";
import { t } from "../../src/i18n";
import { formatBasisPoints, formatDuration, formatMoney, periodOf, weeksPeriod } from "../../src/lib/format";
import { countLabel, seriesMax, tierLabel } from "../../src/lib/kanon";

describe("k-anonymat affiché", () => {
  it("effectif publié par tranche (« 5 à 9 », « 10 à 19 »…), jamais exact", () => {
    expect(tierLabel(5)).toBe("5 à 9 personnes");
    expect(tierLabel(10)).toBe("10 à 19 personnes");
    expect(tierLabel(20)).toBe("20 à 49 personnes");
    expect(tierLabel(50)).toBe("50 à 99 personnes");
    expect(tierLabel(100)).toBe("100 personnes ou plus");
    expect(tierLabel(null)).toBeNull();
  });

  it("compte publié (CR-P3-02) : toujours une tranche, jamais un nombre seul", () => {
    expect(countLabel(5)).toBe("5 à 9");
    expect(countLabel(10)).toBe("10 à 19");
    expect(countLabel(100)).toBe("100 ou plus");
    for (const v of [5, 10, 20, 50, 100]) expect(countLabel(v)).not.toBe(String(v));
  });

  it("l'échelle des barres ignore les valeurs masquées", () => {
    expect(seriesMax([{ status: "masque", value: null, contributors: null }, { status: "disponible", value: 12, contributors: 10 }])).toBe(12);
    expect(seriesMax([{ status: "masque", value: null, contributors: null }])).toBe(0);
  });
});

describe("formats français", () => {
  it("francs CFA entiers, espace fine insécable ; pourcentages ; durées", () => {
    expect(formatMoney(2_380_000)).toBe(t("format.xof", { amount: new Intl.NumberFormat("fr-FR").format(2_380_000) }));
    expect(() => formatMoney(12.5)).toThrow();
    expect(formatBasisPoints(6842)).toBe("68,4 %");
    expect(formatDuration(9_360_000)).toBe("2,6 h");
    expect(formatDuration(1_080_000)).toBe("18 min");
    expect(formatDuration(259_200_000)).toBe("3,0 j");
  });

  it("période en jours locaux, bornes incluses", () => {
    expect(periodOf(30, new Date("2026-10-02T09:00:00Z"))).toEqual({ from: "2026-09-03", to: "2026-10-02" });
  });

  it("semaines entières terminées : lundi → dimanche passé, jamais la semaine en cours", () => {
    // Vendredi 2 octobre 2026 : dernière semaine terminée = lundi 21 → dimanche 27 septembre.
    expect(weeksPeriod(1, new Date("2026-10-02T09:00:00Z"))).toEqual({ from: "2026-09-21", to: "2026-09-27" });
    expect(weeksPeriod(4, new Date("2026-10-02T09:00:00Z"))).toEqual({ from: "2026-08-31", to: "2026-09-27" });
    // Un dimanche, la semaine en cours n'est pas terminée.
    expect(weeksPeriod(1, new Date("2026-09-27T20:00:00Z"))).toEqual({ from: "2026-09-14", to: "2026-09-20" });
  });

  it("catégories : libellé connu, sinon la clé rendue lisible", () => {
    expect(categoryLabel("autres_regroupes")).toBe("Autres catégories regroupées");
    expect(categoryLabel("sante_mentale")).toBe("Sante mentale");
  });
});
