"use client";

import type { MyCard } from "@/api/types";
import { BrandLogo, BrandName } from "@/brand/brand-context";
import { t, tp } from "@/i18n";
import { formatDayMonth, formatRateBp, formatTime } from "@/lib/format";
import { rightsLook, TONE_CLASS } from "@/ui/tones";
import { BrandMark, Guilloche, Icon, Pulse } from "@/ui/ui";
import type { StoredCard } from "./last-card";
import { QrCode } from "./QrCode";
import { qrPhase, type QrPhase, type QrTiming } from "./qr-schedule";

export type CardSource = { kind: "live"; card: MyCard; timing: QrTiming } | { kind: "saved"; card: StoredCard; savedAt: string };

export function phaseOf(source: CardSource, now: number | null): QrPhase {
  if (source.kind === "saved") return "expire";
  // Avant l'hydratation, l'heure n'est pas connue : le QR qui vient d'arriver est valide.
  return now === null ? "valide" : qrPhase(source.timing, now);
}

const RING = 62.83;

/** Anneau or qui se vide jusqu'au prochain QR (décor ; le temps est dit en texte à côté). */
function Ring({ timing, now }: { timing: QrTiming; now: number | null }) {
  const elapsed = now === null || timing.lifetimeMs === 0 ? 0 : Math.min(1, Math.max(0, (now - timing.receivedAt) / timing.lifetimeMs));
  return (
    <svg className="ring" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <circle className="bgc" cx="12" cy="12" r="10" />
      <circle className="fgc" cx="12" cy="12" r="10" transform="rotate(-90 12 12)" style={{ strokeDashoffset: RING * elapsed }} />
    </svg>
  );
}

/** Tuile du QR quand il n'est plus valable : on ne présente jamais un QR périmé. */
function ExpiredQr() {
  return (
    <div className="qr-expired" data-testid="qr-expired">
      <Icon name="clock" />
      <b>{t("card.qr.expired")}</b>
    </div>
  );
}

/**
 * Carte adhérent émeraude profond (planche, écran 03) : guilloche, marque, QR foncé sur blanc,
 * statut des droits (icône + mot), numéro de carte, pouls or et anneau du QR.
 */
export function MemberCard({ source, now, timeZone }: { source: CardSource; now: number | null; timeZone: string }) {
  const { card } = source;
  const phase = phaseOf(source, now);
  const look = rightsLook(card);
  const name = `${card.given_name} ${card.family_name}`;
  let footer: string;
  if (source.kind === "saved") {
    footer = t("card.saved", { day: formatDayMonth(source.savedAt, timeZone), time: formatTime(source.savedAt, timeZone) });
  } else if (phase === "expire") {
    footer = t("card.qr.expired");
  } else if (phase === "a_renouveler") {
    footer = t("card.qr.renewing");
  } else {
    footer = t("card.qr.renewed", { seconds: now === null ? 0 : Math.max(0, Math.floor((now - source.timing.receivedAt) / 1000)) });
  }
  return (
    <article className="mcard" aria-label={t("card.aria", { name })} data-testid="member-card" data-phase={phase}>
      <Guilloche />
      <div className="mc-top">
        <BrandLogo fallback={<BrandMark />} />
        <b>
          <BrandName />
          <small>{t("card.plan", { plan: card.plan_code, rate: formatRateBp(card.coverage_rate_bp) })}</small>
        </b>
      </div>
      <div className="mc-mid">
        <div className="qr-tile">
          {source.kind === "live" && phase !== "expire" ? <QrCode payload={source.card.qr_payload} label={t("card.qr.label", { name })} /> : <ExpiredQr />}
        </div>
        <div className="mc-id">
          <span className={look.tone === "ok" ? "mc-status" : `pill ${TONE_CLASS[look.tone]}`} data-testid="rights">
            <Icon name={look.icon} />
            {t(look.label)}
          </span>
          <p className="mc-name">{name}</p>
          <span className="mc-meta id" data-testid="member-number">
            {card.member_number}
          </span>
          <span className="mc-meta">{tp("card.beneficiaries", card.beneficiaries_count)}</span>
        </div>
      </div>
      <div className="mc-bot">
        <Pulse />
        <span data-testid="qr-footer">{footer}</span>
        {source.kind === "live" && phase === "valide" ? <Ring timing={source.timing} now={now} /> : null}
      </div>
    </article>
  );
}
