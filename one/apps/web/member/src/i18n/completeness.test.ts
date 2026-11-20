import { describe, expect, it } from "vitest";
import fr from "./fr.json";
import { BENEFICIARY_CARD, CLAIM_STATUS, CONTRIBUTION_STATUS } from "@/ui/tones";

/** Clés construites à l'exécution (`channel.${c}`…) : chaque valeur des énumérations du contrat a son texte. */
const keys = new Set(Object.keys(fr));
const PAYMENT_CHANNELS = ["wave", "orange_money", "mtn_momo", "virement", "prelevement_employeur", "simulation"] as const;
const STEP_KEYS = ["demande_recue", "accordee", "virement", "recu"] as const;
const STEP_STATES = ["fait", "en_cours", "a_venir", "refuse", "annule", "sans_objet"] as const;

describe("traductions des énumérations du contrat", () => {
  it("moyens de paiement, liens de parenté, payeurs", () => {
    const wanted = [
      ...PAYMENT_CHANNELS.map((c) => `channel.${c}`),
      ...["virement", "prelevement_employeur", "simulation"].map((c) => `pay.method.${c}`),
      ...["titulaire", "conjoint", "enfant", "autre"].map((r) => `relationship.${r}`),
      ...["adherent", "employeur", "proche"].map((p) => `contribution.payer.${p}`),
    ];
    expect(wanted.filter((k) => !keys.has(k))).toEqual([]);
  });

  it("étapes et états de la frise", () => {
    const wanted = [...STEP_KEYS.map((k) => `tracking.step.${k}`), ...STEP_STATES.map((s) => `tracking.state.${s}`)];
    expect(wanted.filter((k) => !keys.has(k))).toEqual([]);
  });

  it("statuts : dossier, cotisation, carte (libellé présent, jamais le ton d'accent)", () => {
    for (const look of [...Object.values(CLAIM_STATUS), ...Object.values(CONTRIBUTION_STATUS), ...Object.values(BENEFICIARY_CARD)]) {
      expect(keys.has(look.label), look.label).toBe(true);
      expect(["ok", "warn", "crit", "info", "neutral"]).toContain(look.tone);
    }
  });

  it("pluriels : forme .one et .other", () => {
    for (const key of keys) {
      if (key.endsWith(".one")) expect(keys.has(key.replace(/\.one$/, ".other")), key).toBe(true);
    }
  });
});
