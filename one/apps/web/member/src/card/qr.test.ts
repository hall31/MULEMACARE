import { describe, expect, it } from "vitest";
import { card } from "@/test/fixtures";
import { QR_GRACE_MS, qrPhase, qrTiming } from "./qr-schedule";
import { qrModules } from "./qr-matrix";

describe("QR rotatif : rafraîchi avant expiration (Q-P1-04)", () => {
  const received = 1_000_000;

  it("échéance = réception + durée annoncée par le serveur (insensible à l'horloge du téléphone)", () => {
    // Le serveur annonce 30 s ; le téléphone a 2 h d'avance : seule la durée compte.
    const timing = qrTiming({ qr_generated_at: "2026-10-01T09:00:00Z", qr_refresh_at: "2026-10-01T09:00:30Z" }, received);
    expect(timing.refreshAt).toBe(received + 30_000);
    expect(timing.expiresAt).toBe(received + 30_000 + QR_GRACE_MS);
    expect(timing.lifetimeMs).toBe(30_000);
  });

  it("le rafraîchissement part avant l'expiration, avec la marge de la fenêtre de tolérance", () => {
    const timing = qrTiming(card, received);
    expect(timing.refreshAt).toBeLessThan(timing.expiresAt);
    expect(QR_GRACE_MS).toBeGreaterThan(0);
    expect(QR_GRACE_MS).toBeLessThan(30_000);
  });

  it("phases : valide, à renouveler, expiré", () => {
    const timing = qrTiming(card, received);
    expect(qrPhase(timing, received + 1_000)).toBe("valide");
    expect(qrPhase(timing, timing.refreshAt)).toBe("a_renouveler");
    expect(qrPhase(timing, timing.expiresAt - 1)).toBe("a_renouveler");
    expect(qrPhase(timing, timing.expiresAt)).toBe("expire");
  });

  it("durée absurde (négative, illisible, trop longue) : jamais un QR affiché plus de 60 s", () => {
    expect(qrTiming({ qr_generated_at: "2026-10-01T09:00:30Z", qr_refresh_at: "2026-10-01T09:00:00Z" }, received).refreshAt).toBe(received);
    expect(qrTiming({ qr_generated_at: "n'importe quoi", qr_refresh_at: "2026-10-01T09:00:00Z" }, received).refreshAt).toBe(received);
    expect(qrTiming({ qr_generated_at: "2026-10-01T09:00:00Z", qr_refresh_at: "2026-10-01T10:00:00Z" }, received).lifetimeMs).toBe(60_000);
  });
});

describe("dessin du QR", () => {
  it("encode la charge utile (motifs de position aux trois coins), sans couleur dans le tracé", () => {
    const qr = qrModules(card.qr_payload);
    expect(qr.size).toBeGreaterThanOrEqual(21);
    expect((qr.size - 17) % 4).toBe(0);
    // Motif de position : carré 7×7 plein au bord, creux en couronne.
    const at = (x: number, y: number) => qr.dark.has(`${x},${y}`);
    for (const [ox, oy] of [[0, 0], [qr.size - 7, 0], [0, qr.size - 7]] as const) {
      expect(at(ox, oy) && at(ox + 6, oy) && at(ox, oy + 6) && at(ox + 3, oy + 3)).toBe(true);
      expect(at(ox + 1, oy + 1)).toBe(false);
    }
    expect(qr.path).toMatch(/^(M\d+ \d+h\d+v1h-\d+z)+$/);
  });

  it("deux charges utiles différentes donnent deux QR différents ; la même, le même", () => {
    expect(qrModules("MC1.a").path).toBe(qrModules("MC1.a").path);
    expect(qrModules("MC1.a").path).not.toBe(qrModules("MC1.b").path);
  });
});
