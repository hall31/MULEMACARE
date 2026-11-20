import { describe, expect, it } from "vitest";
import { ApiProblem, NetworkTimeout, NetworkUnavailable } from "@/api/client";
import type { Problem } from "@/api/types";
import { card } from "@/test/fixtures";
import type { CardSnapshot, LastCardRead } from "./last-card";
import { chooseCard } from "./source";

const { qr_payload: _p, qr_generated_at: _g, qr_refresh_at: _r, ...stored } = card;
const snapshot: CardSnapshot = { savedAt: "2026-10-01T09:00:05.000Z", card: stored };
const SAVED: LastCardRead = { kind: "fresh", snapshot };
const NOW = Date.parse("2026-10-01T12:00:00Z");

function problem(status: number, code: Problem["code"]): ApiProblem {
  return new ApiProblem(status, { code, message: "", action: "", request_id: "req" });
}

describe("quelle carte afficher", () => {
  it("réponse du serveur : la carte en direct", () => {
    expect(chooseCard({ hasData: true, error: null, saved: SAVED, now: NOW }).kind).toBe("live");
  });

  it("erreur RÉSEAU : la dernière carte enregistrée", () => {
    for (const error of [new NetworkUnavailable(true), new NetworkUnavailable(false), new NetworkTimeout()]) {
      expect(chooseCard({ hasData: false, error, saved: SAVED, now: NOW })).toEqual({ kind: "saved", snapshot });
    }
  });

  // Démonstration du vérificateur : la carte enregistrée restait lisible après AUTH-01 / NOT-01.
  it("session expirée, accès refusé, carte révoquée : jamais la carte enregistrée", () => {
    for (const error of [problem(401, "AUTH-01"), problem(403, "AUTH-02"), problem(404, "NOT-01"), problem(403, "SEC-01"), problem(404, "ID-06")]) {
      expect(chooseCard({ hasData: false, error, saved: SAVED, now: NOW }).kind, error.problem.code).toBe("none");
    }
  });

  it("refus d'accès pendant l'affichage : la carte en direct (gardée en mémoire) disparaît aussi", () => {
    expect(chooseCard({ hasData: true, error: problem(401, "AUTH-01"), saved: SAVED, now: NOW }).kind).toBe("none");
    expect(chooseCard({ hasData: true, error: problem(404, "NOT-01"), saved: SAVED, now: NOW }).kind).toBe("none");
  });

  it("autre erreur du serveur (503 SYS-01) : l'erreur, pas la carte enregistrée", () => {
    expect(chooseCard({ hasData: false, error: problem(503, "SYS-01"), saved: SAVED, now: NOW }).kind).toBe("none");
  });

  it("carte enregistrée de plus de 24 h : message « trop ancienne », sans la carte", () => {
    const old: LastCardRead = { kind: "stale", savedAt: "2026-09-29T09:00:00.000Z" };
    expect(chooseCard({ hasData: false, error: new NetworkUnavailable(true), saved: old, now: NOW })).toEqual({ kind: "too-old", savedAt: old.savedAt });
    // Devenue trop ancienne pendant que l'écran est ouvert.
    const later = Date.parse("2026-10-02T09:00:06Z");
    expect(chooseCard({ hasData: false, error: new NetworkUnavailable(true), saved: SAVED, now: later })).toEqual({ kind: "too-old", savedAt: snapshot.savedAt });
  });

  it("aucune carte enregistrée : rien", () => {
    expect(chooseCard({ hasData: false, error: new NetworkUnavailable(true), saved: { kind: "none" }, now: NOW }).kind).toBe("none");
  });
});
