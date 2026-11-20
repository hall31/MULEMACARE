"use client";

import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { isOfflineError, toUiError } from "@/api/errors";
import { t } from "@/i18n";
import { formatDateOnly, formatDayMonth, formatTime } from "@/lib/format";
import { track } from "@/lib/track";
import { ContributionPanel, LatestClaimPanel } from "@/member/HomePanels";
import { useMyCard, useNow, useOnline, useTimeZone } from "@/member/queries";
import { deferred } from "@/ui/deferred";
import { ErrorState } from "@/ui/states";
import { Button, Icon, Notice, ScreenTitle, Skeleton, useDelayed } from "@/ui/ui";
import { CeilingPanel } from "./CeilingPanel";
import { browserStore, MAX_SAVED_CARD_AGE_MS, readLastCard, type LastCardRead } from "./last-card";
import { MemberCard, phaseOf, type CardSource } from "./MemberCard";
import { requestPresentFullscreen } from "./fullscreen";
import { qrTiming } from "./qr-schedule";
import { chooseCard } from "./source";

/*
 * Hors du JavaScript initial de la carte (PERFORMANCE.md) : l'invitation à la découverte (rien au
 * rendu serveur, elle attend la lecture du téléphone) et l'écran « Présenter ma carte » (ouvert
 * par un geste). Ce dernier est préchargé dès que la carte est là, pour être en cache (service
 * worker) si le réseau tombe ensuite au comptoir.
 */
const TourInvite = deferred(() => import("@/onboarding/TourInvite").then((m) => m.TourInvite));
const PresentCard = deferred(() => import("./PresentCard").then((m) => m.PresentCard));

/**
 * Forme de la carte pendant le chargement : même structure et mêmes hauteurs que la carte (pas de
 * saut de mise en page quand elle arrive) ; les barres n'apparaissent qu'après 300 ms.
 */
function CardSkeleton() {
  const shown = useDelayed(true);
  return (
    <div className="mcard mcard-sk" role="status" aria-live="polite" data-testid="card-loading">
      <span className="sr-only">{t("loading.card")}</span>
      <div className="mc-top sk-block">{shown ? <Skeleton width="55%" /> : null}</div>
      <div className="mc-mid">
        <div className="qr-tile" />
        <div className="stack">
          {shown ? (
            <>
              <Skeleton width="80%" />
              <Skeleton width="60%" />
            </>
          ) : null}
        </div>
      </div>
      <div className="mc-bot" />
    </div>
  );
}

/** Place du plafond familial tant que la carte n'est pas arrivée. */
function CeilingSkeleton() {
  const shown = useDelayed(true);
  return (
    <div className="panel ceiling-sk" aria-hidden="true">
      <div className="panel-h">{shown ? <Skeleton width="50%" /> : null}</div>
      <div className="pad stack">{shown ? <Skeleton width="70%" height="28px" /> : null}</div>
    </div>
  );
}

/**
 * Ma carte (planche, écran 03) : carte émeraude et QR rotatif, statut des droits, « Présenter ma
 * carte au comptoir » en plein écran, plafond familial restant, dernier remboursement et
 * cotisation du mois. Erreur RÉSEAU seulement : dernière carte enregistrée (moins de 24 h), QR
 * clairement expiré. Refus d'accès (session expirée, carte révoquée) : aucune donnée de carte,
 * l'erreur et son code (règle dans `./source.ts`).
 */
export function CardScreen({ personId = null }: { personId?: string | null }) {
  const query = useMyCard(personId);
  const now = useNow();
  const online = useOnline();
  const timeZone = useTimeZone();
  const [saved, setSaved] = useState<LastCardRead>({ kind: "none" });
  const [presenting, setPresenting] = useState(false);
  const presentButton = useRef<HTMLButtonElement>(null);

  // Lue seulement sur une erreur réseau (jamais après un refus d'accès), avant l'affichage : pas
  // d'erreur montrée une image avant la carte enregistrée.
  const offlineError = query.isError && isOfflineError(query.error);
  useLayoutEffect(() => {
    if (!offlineError) {
      setSaved({ kind: "none" });
      return;
    }
    const store = browserStore();
    setSaved(store ? readLastCard(store, personId, Date.now()) : { kind: "none" });
  }, [offlineError, personId]);

  const closePresent = useCallback(() => {
    setPresenting(false);
    presentButton.current?.focus();
  }, []);

  const choice = chooseCard({ hasData: query.data !== undefined, error: query.error, saved, now });
  let source: CardSource | null = null;
  if (choice.kind === "live" && query.data) source = { kind: "live", card: query.data, timing: qrTiming(query.data, query.dataUpdatedAt) };
  else if (choice.kind === "saved") source = { kind: "saved", card: choice.snapshot.card, savedAt: choice.snapshot.savedAt };
  const netCode = query.error && isOfflineError(query.error) ? toUiError(query.error).code : undefined;

  const phase = source ? phaseOf(source, now) : null;
  const blocked = source?.card.card_status === "bloquee";
  const canPresent = source?.kind === "live" && phase !== "expire" && !blocked;
  const self = personId === null;

  useEffect(() => {
    if (presenting && !canPresent) setPresenting(false);
  }, [presenting, canPresent]);

  const live = source?.kind === "live";
  useEffect(() => {
    if (live) PresentCard.preload();
  }, [live]);

  return (
    <div className="m-body" data-testid="card-screen">
      <div className="m-col">
        <p className="eyebrow">{source ? t(self ? "card.greeting" : "card.of", { name: source.card.given_name }) : t(self ? "card.eyebrow" : "card.eyebrow.other")}</p>
        <ScreenTitle>{t(self ? "card.title" : "card.title.other")}</ScreenTitle>
        {!self ? (
          <Link className="link-row link-back" href="/famille">
            <Icon name="back" />
            <span>{t("card.backToFamily")}</span>
          </Link>
        ) : null}

        {source ? <MemberCard source={source} now={now} timeZone={timeZone} /> : null}
        {!source && !query.isError ? <CardSkeleton /> : null}

        {source?.kind === "saved" ? (
          <Notice tone="warn" icon="wifiOff" title={t("card.offline.title", { day: formatDayMonth(source.savedAt, timeZone), time: formatTime(source.savedAt, timeZone) })} testId="card-offline" code={netCode}>
            <p>{t("card.offline.qr")}</p>
            <p className="detail">{t("card.offline.number", { number: source.card.member_number })}</p>
          </Notice>
        ) : null}
        {choice.kind === "too-old" ? (
          <Notice tone="warn" icon="clock" title={t("card.tooOld.title")} testId="card-too-old" code={netCode}>
            <p>{t("card.tooOld.detail", { day: formatDayMonth(choice.savedAt, timeZone), time: formatTime(choice.savedAt, timeZone), hours: MAX_SAVED_CARD_AGE_MS / 3_600_000 })}</p>
            <p className="detail">{t("card.tooOld.action")}</p>
          </Notice>
        ) : null}
        {source?.kind === "live" && phase === "expire" ? (
          <Notice tone="warn" icon="clock" title={t("card.qr.expired.title")} testId="qr-expired-notice" code={query.error ? (isOfflineError(query.error) ? (online ? "E-NET-02" : "E-NET-01") : undefined) : undefined}>
            <p>{t("card.qr.expired.detail")}</p>
            <p className="detail">{t("card.offline.number", { number: source.card.member_number })}</p>
          </Notice>
        ) : null}
        {blocked && source?.card.blocked_until ? (
          <Notice tone="crit" icon="lock" title={t("card.blocked.title", { time: formatTime(source.card.blocked_until, timeZone) })} code="ID-04" testId="card-blocked">
            <p>{t("card.blocked.detail")}</p>
          </Notice>
        ) : null}
        {source && !blocked && !source.card.entitlements.rights_open ? (
          <Notice
            tone={source.card.entitlements.status === "carence" ? "warn" : "crit"}
            title={source.card.entitlements.status === "carence" ? t("card.waiting.title", { date: formatDateOnly(source.card.entitlements.waiting_period_ends_on) }) : t("card.closed.title")}
            code="R-01"
            testId="rights-notice"
          >
            <p>{t(source.card.entitlements.status === "carence" ? "card.waiting.detail" : "card.closed.detail")}</p>
          </Notice>
        ) : null}
        {query.isError && !source && choice.kind !== "too-old" ? <ErrorState title={t("error.title.card")} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} testId="card-error" /> : null}

        <Button ref={presentButton} variant="primary" icon="qr" className="btn-block" disabled={!canPresent} aria-disabled={!canPresent || undefined} onClick={() => {
          requestPresentFullscreen();
          setPresenting(true);
          track("card_presented", { variant: "en_ligne" });
        }}>
          {t("card.present")}
        </Button>
        <p className="m-hint">{t("card.hint")}</p>
        {self ? <TourInvite /> : null}
      </div>

      <div className="m-col">
        {source ? <CeilingPanel entitlements={source.card.entitlements} /> : null}
        {!source && !query.isError ? <CeilingSkeleton /> : null}
        {self ? (
          <>
            <LatestClaimPanel />
            <ContributionPanel />
          </>
        ) : null}
      </div>

      {presenting && source?.kind === "live" ? <PresentCard card={source.card} timing={source.timing} now={now} onClose={closePresent} /> : null}
    </div>
  );
}
