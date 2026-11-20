"use client";

import { useEffect, useState } from "react";
import type { QrModules } from "./qr-matrix";

/**
 * QR de la carte, foncé sur blanc dans tous les thèmes (contrat §9). L'encodeur (uqr) est chargé
 * à part, après les données : il ne pèse pas sur le premier affichage. Dimensions réservées par
 * le conteneur (pas de saut de mise en page).
 */
export function QrCode({ payload, label, margin = 2, testId = "qr" }: { payload: string; label: string; margin?: number; testId?: string }) {
  const [qr, setQr] = useState<{ payload: string; modules: QrModules } | null>(null);

  useEffect(() => {
    let alive = true;
    void import("./qr-matrix").then(({ qrModules }) => {
      if (alive) setQr({ payload, modules: qrModules(payload) });
    });
    return () => {
      alive = false;
    };
  }, [payload]);

  const ready = qr !== null && qr.payload === payload;
  const size = ready ? qr.modules.size : 25;
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`${-margin} ${-margin} ${size + 2 * margin} ${size + 2 * margin}`}
      shapeRendering="crispEdges"
      className="qr"
      data-testid={testId}
      data-ready={ready || undefined}
    >
      <rect className="qr-bg" x={-margin} y={-margin} width={size + 2 * margin} height={size + 2 * margin} />
      {ready ? <path className="qr-m" d={qr.modules.path} /> : null}
    </svg>
  );
}
