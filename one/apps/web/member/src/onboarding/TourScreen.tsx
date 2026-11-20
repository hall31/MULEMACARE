"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { isOfflineError } from "@/api/errors";
import type { MyCard } from "@/api/types";
import { browserStore, readLastCard, type StoredCard } from "@/card/last-card";
import { t, tp, type MessageKey } from "@/i18n";
import { formatDayMonth, formatRateBp, formatTime, formatXof } from "@/lib/format";
import { track } from "@/lib/track";
import { useClaims, useMyCard, useTimeZone } from "@/member/queries";
import { ErrorState, LoadingState } from "@/ui/states";
import { rightsLook } from "@/ui/tones";
import { Button, Icon, Pill, ScreenTitle } from "@/ui/ui";
import { TOUR_STEPS, checkChoices, coverageExample, writeTour, type TourState, type TourStep } from "./tour";

const TITLES: Record<TourStep, MessageKey> = {
  couverture: "tour.step.couverture.title",
  carte: "tour.step.carte.title",
  suivi: "tour.step.suivi.title",
};

type CardForTour = StoredCard | MyCard;

/** Carte en direct, sinon (erreur réseau seulement) la dernière carte enregistrée sur le téléphone. */
function useTourCard(): { card: CardForTour | null; savedAt: string | null; pending: boolean; error: unknown; retry: () => void; retrying: boolean } {
  const query = useMyCard(null);
  const [saved, setSaved] = useState<{ card: StoredCard; savedAt: string } | null>(null);
  const offline = query.isError && isOfflineError(query.error);
  useEffect(() => {
    if (!offline) {
      setSaved(null);
      return;
    }
    const store = browserStore();
    const read = store ? readLastCard(store, null, Date.now()) : null;
    setSaved(read?.kind === "fresh" ? read.snapshot : null);
  }, [offline]);
  if (query.data) return { card: query.data, savedAt: null, pending: false, error: null, retry: () => undefined, retrying: false };
  if (saved) return { card: saved.card, savedAt: saved.savedAt, pending: false, error: null, retry: () => void query.refetch(), retrying: query.isFetching };
  return { card: null, savedAt: null, pending: query.isPending, error: query.isError ? query.error : null, retry: () => void query.refetch(), retrying: query.isFetching };
}

/** Étape 1 : ce que la mutuelle rembourse et à quel taux, depuis la carte (getMyCard) et son plafond. */
function CoverageStep() {
  const { card, savedAt, pending, error, retry, retrying } = useTourCard();
  const timeZone = useTimeZone();
  const [answer, setAnswer] = useState<number | null>(null);
  const groupId = useId();

  if (pending) return <LoadingState label={t("loading.card")} rows={4} testId="tour-loading" />;
  if (!card) return <ErrorState title={t("error.title.card")} error={error} onRetry={retry} retrying={retrying} testId="tour-error" />;

  const rate = formatRateBp(card.coverage_rate_bp);
  const example = coverageExample(card.coverage_rate_bp);
  const money = { total: formatXof(example.total), covered: formatXof(example.covered), patient: formatXof(example.patient) };
  const choices = checkChoices(card.coverage_rate_bp);
  const chosen = choices.find((c) => c.amount === answer);
  const ent = card.entitlements;

  return (
    <div className="stack" data-testid="tour-coverage">
      {savedAt ? (
        <p className="alert tone-warn" role="status" data-testid="tour-saved">
          <Icon name="wifiOff" />
          <span>{t("tour.couverture.saved", { day: formatDayMonth(savedAt, timeZone), time: formatTime(savedAt, timeZone) })}</span>
        </p>
      ) : null}
      <section className="panel" aria-labelledby="tour-rate-t">
        <div className="panel-h">
          <h2 className="panel-t" id="tour-rate-t">
            {t("tour.couverture.lead", { plan: card.plan_code })}
          </h2>
          <Pill look={rightsLook(card)} testId="tour-rights" />
        </div>
        <div className="pad stack">
          <p className="tour-rate">
            <span className="amount money-display" data-testid="tour-rate">
              {rate}
            </span>
          </p>
          <p>
            <b>{t("tour.couverture.rate", { rate })}</b>
          </p>
          <p>{t("tour.couverture.where")}</p>
          <p data-testid="tour-example">{t("tour.couverture.example", money)}</p>
          <p data-testid="tour-ceiling">
            {t("tour.couverture.ceiling", { ceiling: formatXof(ent.family_annual_ceiling_xof), remaining: formatXof(ent.remaining_xof) })}
          </p>
          <p>{tp("tour.couverture.family", card.beneficiaries_count)}</p>
        </div>
      </section>

      <fieldset className="p-methods" data-testid="tour-check" aria-describedby={chosen ? `${groupId}-fb` : undefined}>
        <legend>{t("tour.check.question", { total: money.total })}</legend>
        {choices.map((choice) => (
          <label key={choice.amount} className="method">
            <input type="radio" name={`${groupId}-check`} value={choice.amount} checked={answer === choice.amount} onChange={() => setAnswer(choice.amount)} />
            <span>
              <b className="amount">{formatXof(choice.amount)}</b>
            </span>
            <span />
          </label>
        ))}
      </fieldset>
      {chosen ? (
        <p id={`${groupId}-fb`} role="status" className={`alert ${chosen.correct ? "tone-ok" : "tone-warn"}`} data-testid="tour-feedback" data-correct={chosen.correct}>
          <Icon name={chosen.correct ? "check" : "info"} />
          <span>{t(chosen.correct ? "tour.check.right" : "tour.check.wrong", money)}</span>
        </p>
      ) : null}
    </div>
  );
}

/** Étape 2 : présenter sa carte au comptoir (QR, photo, code SMS). */
function PresentStep() {
  const { card } = useTourCard();
  return (
    <div className="stack" data-testid="tour-present">
      <p>{t("tour.carte.lead")}</p>
      <ol className="p-steps tour-steps">
        <li>
          <span>{t("tour.carte.1")}</span>
        </li>
        <li>
          <span>{t("tour.carte.2")}</span>
        </li>
        <li>
          <span>{t("tour.carte.3")}</span>
        </li>
      </ol>
      <p className="alert tone-info">
        <Icon name="qr" />
        <span>{t("tour.carte.qr")}</span>
      </p>
      <p className="alert tone-neutral">
        <Icon name="wifiOff" />
        <span>{card ? t("tour.carte.offline", { number: card.member_number }) : t("tour.carte.offline.generic")}</span>
      </p>
    </div>
  );
}

const TRACK_STEPS = [
  { key: "demande_recue", title: "tracking.step.demande_recue", text: "tour.suivi.demande_recue" },
  { key: "accordee", title: "tracking.step.accordee", text: "tour.suivi.accordee" },
  { key: "virement", title: "tracking.step.virement", text: "tour.suivi.virement" },
  { key: "recu", title: "tracking.step.recu", text: "tour.suivi.recu" },
] as const satisfies readonly { key: string; title: MessageKey; text: MessageKey }[];

/** Étape 3 : suivre un remboursement (la frise des quatre étapes, puis le dernier dossier). */
function TrackStep() {
  const claims = useClaims();
  const latest = claims.data?.pages[0]?.items[0] ?? null;
  return (
    <div className="stack" data-testid="tour-track">
      <p>{t("tour.suivi.lead")}</p>
      <ol className="tl">
        {TRACK_STEPS.map((step) => (
          <li key={step.key}>
            <span className="tl-dot" aria-hidden="true" />
            <div>
              <b>{t(step.title)}</b>
              <span>{t(step.text)}</span>
            </div>
          </li>
        ))}
      </ol>
      {latest ? (
        <Link className="link-row" href={`/soins/${latest.id}`}>
          <span>{t("tour.suivi.latest")}</span>
          <Icon name="chev" />
        </Link>
      ) : null}
      {!latest && claims.isSuccess ? <p>{t("tour.suivi.none")}</p> : null}
    </div>
  );
}

/**
 * Découverte de l'espace (première visite, Phase 2 voie A) : trois étapes, passable à tout moment,
 * rejouable depuis « Ma carte ». Une question par écran, une seule action principale (Suivant ou
 * Terminer), 48 px partout. L'étape suivante remonte le focus sur son titre.
 */
export function TourScreen() {
  const router = useRouter();
  const [index, setIndex] = useState(0);
  const step = TOUR_STEPS[index] ?? "couverture";
  const total = TOUR_STEPS.length;
  const last = index === total - 1;
  const startedAt = useRef<number | null>(null);

  // Mesure produit : début, chaque étape vue, fin (durée seulement ; aucune réponse envoyée).
  useEffect(() => {
    startedAt.current = performance.now();
    track("onboarding_started");
  }, []);
  useEffect(() => {
    track("onboarding_step", { step: index + 1 });
  }, [index]);

  const leave = (state: TourState) => {
    const store = browserStore();
    if (store) writeTour(store, state, new Date());
    if (state === "termine") track("onboarding_completed", { duration_ms: performance.now() - (startedAt.current ?? performance.now()) });
    router.push("/");
  };

  return (
    <div className="m-body m-single" data-testid="tour" data-step={step}>
      <div className="m-col">
        {/* Clé d'étape sur le contenu seulement : les boutons restent montés, le titre reprend le focus. */}
        <div className="m-col" key={step}>
          <p className="eyebrow">{t("tour.eyebrow", { n: index + 1, total })}</p>
          <ScreenTitle>{t(TITLES[step])}</ScreenTitle>
          <div className="tour-progress" aria-hidden="true">
            {TOUR_STEPS.map((s, i) => (
              <i key={s} data-done={i <= index || undefined} />
            ))}
          </div>
          {step === "couverture" ? <CoverageStep /> : null}
          {step === "carte" ? <PresentStep /> : null}
          {step === "suivi" ? <TrackStep /> : null}
        </div>

        <div className="actions tour-actions">
          {index > 0 ? (
            <Button variant="secondary" icon="back" onClick={() => setIndex(index - 1)}>
              {t("tour.prev")}
            </Button>
          ) : null}
          <Button variant="secondary" onClick={() => leave("passe")} data-testid="tour-skip">
            {t("tour.skip")}
          </Button>
        </div>
        <Button variant="primary" className="btn-block" trailing={last ? "check" : "arrow"} onClick={() => (last ? leave("termine") : setIndex(index + 1))} data-testid="tour-next">
          {t(last ? "tour.finish" : "tour.next")}
        </Button>
      </div>
    </div>
  );
}
