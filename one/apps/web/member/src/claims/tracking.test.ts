import { describe, expect, it } from "vitest";
import { IDS, trackings } from "@/test/fixtures";
import { trackingView } from "./tracking";
import fr from "@/i18n/fr.json";

const TZ = "Africa/Abidjan";

describe("frise du remboursement : demande reçue → accordée → virement → reçu", () => {
  it("quatre étapes dans l'ordre du contrat", () => {
    const steps = trackingView(trackings[IDS.claimPharmacy]?.steps ?? [], TZ);
    expect(steps.map((s) => s.key)).toEqual(["demande_recue", "accordee", "virement", "recu"]);
  });

  it("étape faite : datée en heure locale, avec le code public de la règle", () => {
    const [received, granted] = trackingView(trackings[IDS.claimPharmacy]?.steps ?? [], TZ);
    expect(received).toMatchObject({ look: "done", detail: "28/09 · 14:51" });
    expect(granted?.look).toBe("done");
    expect(granted?.detail).toContain("R-12 v3");
  });

  it("étape sans donnée (virement non daté, Q-P1-03) : « en cours », jamais une date inventée", () => {
    const transfer = trackingView(trackings[IDS.claimPharmacy]?.steps ?? [], TZ)[2];
    expect(transfer?.look).toBe("current");
    expect(transfer?.detail).toBe(fr["tracking.state.en_cours"]);
    expect(transfer?.detail).not.toMatch(/\d/);
  });

  it("dossier payé : virement et réception faits, sans date (le contrat ne les date pas)", () => {
    const [, , transfer, received] = trackingView(trackings[IDS.claimClinic]?.steps ?? [], TZ);
    expect(transfer).toMatchObject({ look: "done", detail: fr["tracking.state.fait"] });
    expect(received).toMatchObject({ look: "done", detail: fr["tracking.state.fait"] });
  });

  it("refus : cachet critique, motif par son code ; les étapes suivantes sont sans objet", () => {
    const [, decision, transfer, received] = trackingView(trackings[IDS.claimRefused]?.steps ?? [], TZ);
    expect(decision?.look).toBe("refused");
    expect(decision?.title).toBe(fr["tracking.step.accordee.refuse"]);
    expect(decision?.detail).toContain("R-04 v2");
    expect(transfer?.look).toBe("na");
    expect(received?.detail).toBe(fr["tracking.state.sans_objet"]);
  });

  it("décision humaine sans règle : seul le code de motif sort (MC-02)", () => {
    const view = trackingView(
      [
        { key: "demande_recue", state: "fait", at: "2026-09-01T10:00:00Z", rule: null, reason_code: null },
        { key: "accordee", state: "fait", at: "2026-09-02T10:00:00Z", rule: null, reason_code: "MC-02" },
        { key: "virement", state: "en_cours", at: null, rule: null, reason_code: null },
        { key: "recu", state: "a_venir", at: null, rule: null, reason_code: null },
      ],
      TZ,
    );
    expect(view[1]?.detail).toContain("MC-02");
    expect(view[3]).toMatchObject({ look: "todo", detail: fr["tracking.state.a_venir"] });
  });

  it("chaque étape dit son état en mots (jamais la couleur seule)", () => {
    for (const tracking of Object.values(trackings)) {
      for (const step of trackingView(tracking.steps, TZ)) {
        expect(step.title.length).toBeGreaterThan(3);
        expect(step.stateLabel.length).toBeGreaterThan(3);
      }
    }
  });
});
