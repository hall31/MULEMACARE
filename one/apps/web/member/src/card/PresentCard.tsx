"use client";

import { useEffect, useRef } from "react";
import type { MyCard } from "@/api/types";
import { t } from "@/i18n";
import { Button, Icon } from "@/ui/ui";
import { QrCode } from "./QrCode";
import { qrPhase, type QrTiming } from "./qr-schedule";

interface WakeLockSentinelLike {
  release(): Promise<void>;
}
type WakeLockNavigator = Navigator & { wakeLock?: { request(type: "screen"): Promise<WakeLockSentinelLike> } };

/**
 * « Présenter ma carte au comptoir » : QR en grand, foncé sur blanc quel que soit le thème,
 * écran maintenu allumé (Wake Lock) et plein écran si le navigateur le permet. Aucune API web
 * ne règle la luminosité : le fond blanc maximal la remplace, et l'adhérent est invité à monter
 * la luminosité. Le QR continue de tourner (même requête que la carte).
 */
export function PresentCard({ card, timing, now, onClose }: { card: MyCard; timing: QrTiming; now: number | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const name = `${card.given_name} ${card.family_name}`;
  const phase = now === null ? "valide" : qrPhase(timing, now);
  const seconds = now === null ? null : Math.min(Math.ceil(timing.lifetimeMs / 1000), Math.max(0, Math.ceil((timing.refreshAt - now) / 1000)));

  useEffect(() => {
    closeRef.current?.focus();
    let lock: WakeLockSentinelLike | null = null;
    let released = false;
    (navigator as WakeLockNavigator).wakeLock
      ?.request("screen")
      .then((sentinel) => {
        if (released) void sentinel.release().catch(() => undefined);
        else lock = sentinel;
      })
      .catch(() => undefined);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      // Un seul contrôle dans la fenêtre : la tabulation y reste.
      if (event.key === "Tab") {
        event.preventDefault();
        closeRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    document.body.dataset.presenting = "";
    return () => {
      released = true;
      void lock?.release().catch(() => undefined);
      document.removeEventListener("keydown", onKey);
      delete document.body.dataset.presenting;
      if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    };
  }, [onClose]);

  return (
    <div className="present" role="dialog" aria-modal="true" aria-labelledby="present-t" aria-describedby="present-d" data-testid="present">
      <div className="present-in">
        <h2 id="present-t" className="present-name">
          {name}
        </h2>
        <span className="present-id id">{card.member_number}</span>
        <div className="present-qr">
          {phase === "expire" ? (
            <div className="qr-expired" data-testid="qr-expired">
              <Icon name="clock" />
              <b>{t("card.qr.expired")}</b>
            </div>
          ) : (
            <QrCode payload={card.qr_payload} label={t("card.qr.label", { name })} margin={4} testId="present-qr" />
          )}
        </div>
        <p id="present-d" className="present-say">
          {t("present.instruction")}
        </p>
        <p className="present-hint">
          <Icon name="sun" />
          <span>{t("present.brightness")}</span>
        </p>
        <p className="present-hint" data-testid="present-countdown">
          <Icon name="refresh" />
          <span>{phase === "valide" && seconds !== null ? t("present.next", { seconds }) : t("card.qr.renewing")}</span>
        </p>
        <Button ref={closeRef} variant="secondary" icon="x" onClick={onClose} className="present-close">
          {t("present.close")}
        </Button>
      </div>
    </div>
  );
}
