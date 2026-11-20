"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiProblem, NetworkUnavailable } from "@/api/client";
import { BrandLogo, useBrand } from "@/brand/brand-context";
import type { Identification } from "@/api/types";
import { t, tp } from "@/i18n";
import { formatTime, formatXof, localDate } from "@/lib/format";
import { decisionVariant, track } from "@/lib/telemetry";
import { evaluateOffline, isPolicyFresh, tariffAt } from "@/offline/policy";
import { issueProvisional } from "@/offline/queue";
import { CoachMark } from "./CoachMark";
import { MeasureConsent, MeasureSwitchRow } from "./MeasureConsent";
import { toUiMessage, type UiMessage } from "./errors";
import { HELP_STEPS, disableHelp, enableHelp, markSeen, readHelp, shouldShowHelp, writeHelp, type HelpState } from "./help";
import { offlineCapabilities } from "./offline-capabilities";
import { recordFor, type Outcome } from "./outcome";
import { ActsScreen } from "./screens/ActsScreen";
import { CardScreen } from "./screens/CardScreen";
import { CodeScreen } from "./screens/CodeScreen";
import { DecisionScreen } from "./screens/DecisionScreen";
import { IdentityScreen } from "./screens/IdentityScreen";
import { type StepName, BrandMark, Icon, Notice, Pill, Skeleton, StepHeader, useDelayed } from "./ui";
import { STATUS_TONE_CLASSES, SYNC_TONE } from "./tones";
import { useCounterRuntime, type CounterRuntime } from "./useCounterRuntime";

type Step = StepName;
const STEPS: readonly Step[] = ["card", "identity", "code", "acts", "decision"];
const SUN_STORAGE_KEY = "mulema.sun";

interface Flash {
  tone: "ok" | "warn" | "crit";
  message: UiMessage;
}

function useSunMode(): [boolean, () => void] {
  const [sun, setSun] = useState(false);
  useEffect(() => {
    setSun(window.localStorage.getItem(SUN_STORAGE_KEY) === "1");
  }, []);
  useEffect(() => {
    const root = document.documentElement;
    if (sun) root.setAttribute("data-sun", "");
    else root.removeAttribute("data-sun");
  }, [sun]);
  const toggle = useCallback(() => {
    setSun((current) => {
      const next = !current;
      window.localStorage.setItem(SUN_STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }, []);
  return [sun, toggle];
}

/** Aide de première utilisation : lue après le montage (rien au rendu serveur, pas de saut). */
function useHelp(): [HelpState | null, (next: HelpState) => void] {
  const [help, setHelp] = useState<HelpState | null>(null);
  useEffect(() => {
    setHelp(readHelp(window.localStorage));
  }, []);
  const update = useCallback((next: HelpState) => {
    writeHelp(window.localStorage, next);
    setHelp(next);
  }, []);
  return [help, update];
}

function TopBar({ runtime, sun, onToggleSun, helpOn, onToggleHelp }: { runtime: CounterRuntime; sun: boolean; onToggleSun: () => void; helpOn: boolean; onToggleHelp: () => void }) {
  const brand = useBrand();
  const title = brand?.displayName ?? runtime.me?.organization.name ?? t("app.name");
  const user = runtime.me?.user.display_name ?? t("app.defaultUser");
  const loading = useDelayed(runtime.meLoading);
  return (
    <header className="c-bar">
      <BrandLogo fallback={<BrandMark />} />
      {loading ? (
        <div className="c-who" role="status">
          <span className="sr-only">{t("app.loading")}</span>
          <Skeleton width="70%" />
          <span className="mt-2 block">
            <Skeleton width="45%" />
          </span>
        </div>
      ) : (
        <div className="c-who">
          <b data-testid="brand-name">{title}</b>
          <span>{user}</span>
        </div>
      )}
      <button type="button" aria-pressed={helpOn} aria-label={t("bar.help.label")} title={t("bar.help.short")} onClick={onToggleHelp} className="icobtn" data-testid="help-toggle">
        <Icon name="help" />
      </button>
      <button type="button" aria-pressed={sun} aria-label={t("bar.sun.label")} title={t("bar.sun.short")} onClick={onToggleSun} className="icobtn">
        <Icon name="sun" />
      </button>
    </header>
  );
}

/** Frise d'étapes : décor (l'étape est dite en texte dans chaque écran). */
function Progress({ done, wide }: { done: number; wide: boolean }) {
  return (
    <div className="c-prog" aria-hidden="true" data-testid="progress" data-done-steps={done} data-wide={wide || undefined}>
      {STEPS.map((step, i) => (
        <i key={step} data-done={i < done || undefined} />
      ))}
    </div>
  );
}

/**
 * Bandeau hors ligne persistant (contrat §8) : la situation en une phrase, puis ce qui reste
 * possible et ce qui ne l'est pas, selon l'étape et la politique hors ligne de l'appareil.
 */
function OfflineBanner({ identified, canSign, runtime }: { identified: boolean; canSign: boolean; runtime: CounterRuntime }) {
  // Mesure produit : bandeau vu (compté au retour du réseau, rien ne part hors ligne).
  useEffect(() => track("offline_banner_seen"), []);
  const policy = canSign ? runtime.policy : null;
  const caps = offlineCapabilities({ identified, canSign: policy !== null, thresholdXof: policy?.threshold_xof ?? null, validityMinutes: policy?.validity_minutes ?? null });
  const render = (line: (typeof caps.can)[number]) => {
    const params = line.params ? { ...line.params } : undefined;
    if (params && typeof params.threshold === "number") params.threshold = formatXof(params.threshold);
    return t(line.key, params);
  };
  return (
    <div role="status" data-testid="offline-banner" className={`alert banner ${STATUS_TONE_CLASSES.warn}`}>
      <Icon name="wifiOff" />
      <div className="alert-body">
        <b data-testid="offline-banner-title">
          {!identified
            ? t("net.offline.identification")
            : policy
              ? t("net.offline.withPolicy", { threshold: formatXof(policy.threshold_xof) })
              : t("net.offline.noPolicy")}
        </b>
        <ul className="caps">
          {caps.can.map((line) => (
            <li key={line.key} data-testid="offline-can">
              <Icon name="check" />
              <span>
                <b>{t("net.can.title")}</b> {render(line)}
              </span>
            </li>
          ))}
          {caps.cannot.map((line) => (
            <li key={line.key} data-testid="offline-cannot">
              <Icon name="x" />
              <span>
                <b>{t("net.cannot.title")}</b> {render(line)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function NetworkBanner({ runtime, identified }: { runtime: CounterRuntime; identified: boolean }) {
  const pending = runtime.queue.filter((r) => r.status === "en_attente").length;
  const rejected = runtime.queue.filter((r) => r.status === "rejetee");
  const canSign = runtime.policy !== null && runtime.device !== null && isPolicyFresh(runtime.policyFetchedAt, new Date());
  return (
    <div className="flex flex-col" aria-live="polite">
      {!runtime.online ? <OfflineBanner identified={identified} canSign={canSign} runtime={runtime} /> : null}
      {pending > 0 ? (
        <p role="status" data-testid="sync-banner" className={`alert banner ${STATUS_TONE_CLASSES[SYNC_TONE[runtime.syncState]]}`}>
          <Icon name={runtime.syncState === "error" ? "alert" : "clock"} />
          <span>{runtime.syncState === "syncing" ? t("sync.syncing") : runtime.syncState === "error" ? t("sync.error") : tp("sync.pending", pending)}</span>
        </p>
      ) : null}
      {rejected.length > 0 ? (
        <p role="alert" className={`alert banner ${STATUS_TONE_CLASSES.crit}`}>
          <Icon name="alert" />
          <span>{tp("sync.rejected", rejected.length, { codes: [...new Set(rejected.map((r) => r.reason_code ?? ""))].join(", ") })}</span>
        </p>
      ) : null}
    </div>
  );
}

export function CounterApp() {
  const runtime = useCounterRuntime();
  const { api } = runtime;
  const [sun, toggleSun] = useSunMode();
  const [help, setHelp] = useHelp();
  // Mesure produit : scan ou saisie du numéro → écran de décision (objectif < 10 s, PRD objectif 1).
  const scanStartedAt = useRef<number | null>(null);
  const helpStarted = useRef(false);
  useEffect(() => {
    if (!help || helpStarted.current || help.off || help.seen.length > 0) return;
    helpStarted.current = true;
    track("onboarding_started");
  }, [help]);
  const gotIt = (state: HelpState, current: Step) => {
    const next = markSeen(state, current);
    setHelp(next);
    track("onboarding_step", { step: HELP_STEPS.indexOf(current) + 1 });
    if (HELP_STEPS.every((s) => next.seen.includes(s))) track("onboarding_completed");
  };
  const [step, setStep] = useState<Step>("card");
  const [identification, setIdentification] = useState<Identification | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const [flash, setFlash] = useState<Flash | null>(null);
  const [busy, setBusy] = useState(false);

  const serviceDate = localDate(new Date(), runtime.timeZone);
  const tariff = useMemo(() => (runtime.policy ? tariffAt(runtime.policy, serviceDate) : []), [runtime.policy, serviceDate]);

  const go = useCallback((next: Step) => {
    setStep(next);
    window.scrollTo({ top: 0 });
  }, []);

  const reset = useCallback(() => {
    setIdentification(null);
    setSelected([]);
    setOutcome(null);
    setIdempotencyKey(null);
    go("card");
  }, [go]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setFlash(null);
    try {
      await action();
    } finally {
      setBusy(false);
    }
  }

  const fail = (error: unknown) => setFlash({ tone: "crit", message: toUiMessage(error) });

  function startIdentification(body: { member_number: string } | { qr_payload: string }) {
    scanStartedAt.current = performance.now();
    void run(async () => {
      try {
        const opened = await api.startIdentification(body);
        setIdentification(opened);
        go("identity");
      } catch (error) {
        fail(error);
      }
    });
  }

  function confirmIdentity(confirmed: boolean) {
    if (!identification) return;
    void run(async () => {
      if (!confirmed) {
        try {
          await api.confirmPhoto(identification.id, { confirmed: false });
          reset();
          setFlash({ tone: "crit", message: { text: t("identity.refused") } });
        } catch (error) {
          reset();
          fail(error);
        }
        return;
      }
      try {
        const updated = await api.confirmPhoto(identification.id, { confirmed: true });
        setIdentification(updated);
        await api.sendCode(identification.id);
        go("code");
      } catch (error) {
        fail(error);
      }
    });
  }

  function blocked(error: unknown): boolean {
    if (!(error instanceof ApiProblem) || error.problem.code !== "ID-04") return false;
    const message = toUiMessage(error);
    const seconds = error.problem.retry_after_seconds;
    const until = typeof seconds === "number" ? t("code.blockedUntil", { time: formatTime(new Date(Date.now() + seconds * 1000).toISOString(), runtime.timeZone) }) : undefined;
    reset();
    setFlash({ tone: "crit", message: { text: message.text, detail: [until, message.detail].filter(Boolean).join(" ") } });
    return true;
  }

  function verifyCode(code: string) {
    if (!identification) return;
    void run(async () => {
      try {
        const verified = await api.verifyCode(identification.id, { code });
        setIdentification(verified);
        if (verified.status === "verifiee") go("acts");
      } catch (error) {
        if (!blocked(error)) fail(error);
      }
    });
  }

  function resendCode() {
    if (!identification) return;
    void run(async () => {
      try {
        await api.sendCode(identification.id);
        setFlash({ tone: "ok", message: { text: t("code.resent") } });
      } catch (error) {
        if (!blocked(error)) fail(error);
      }
    });
  }

  function toggleAct(code: string) {
    setIdempotencyKey(null);
    setSelected((current) => (current.includes(code) ? current.filter((c) => c !== code) : [...current, code]));
  }

  function submitActs() {
    if (!identification) return;
    if (selected.length === 0) {
      setFlash({ tone: "crit", message: { text: t("acts.none") } });
      return;
    }
    // Ordre du barème, une ligne par acte coché.
    const codes = tariff.map((i) => i.act_code).filter((c) => selected.includes(c));
    const key = idempotencyKey ?? crypto.randomUUID();
    setIdempotencyKey(key);
    void run(async () => {
      try {
        const created = await api.createClaim({ identification_id: identification.id, service_date: serviceDate, items: codes.map((act_code) => ({ act_code, quantity: 1 })) }, key);
        setOutcome({ kind: "online", created });
        go("decision");
      } catch (error) {
        if (!(error instanceof NetworkUnavailable)) {
          fail(error);
          return;
        }
        // Réseau coupé : accord provisoire signé sur l'appareil, sous le seuil seulement (R13).
        const evaluation = evaluateOffline({ policy: runtime.policy, policyFetchedAt: runtime.policyFetchedAt, deviceId: runtime.device?.id ?? null, identification, selectedActs: codes, serviceDate, now: new Date() });
        if (!evaluation.allowed || !runtime.db || !runtime.device) {
          setOutcome({ kind: "offline_refused", reason: evaluation.allowed ? "no_device" : evaluation.reason, ...(evaluation.allowed || !evaluation.quote ? {} : { quote: evaluation.quote }) });
          go("decision");
          return;
        }
        try {
          const record = await issueProvisional({ db: runtime.db, deviceId: runtime.device.id, privateKey: runtime.device.privateKey, identification, decision: evaluation, serviceDate, policy: evaluation.policy });
          await runtime.refreshQueue();
          setOutcome({ kind: "provisional", offlineRef: record.offline_ref, quote: evaluation.quote, expiresAt: evaluation.expiresAt });
          go("decision");
        } catch (signError) {
          fail(signError);
        }
      }
    });
  }

  function nextPatient() {
    void runtime.purge();
    setFlash(null);
    reset();
  }

  useEffect(() => {
    if (step !== "decision" || !outcome) return;
    const variant = decisionVariant(outcome.kind === "online" ? { kind: "online", status: outcome.created.claim.status } : outcome);
    if (variant && scanStartedAt.current !== null) track("counter_decision_shown", { variant, duration_ms: performance.now() - scanStartedAt.current });
  }, [step, outcome]);

  const index = STEPS.indexOf(step);
  // Étapes franchies, étape en cours comprise ; la décision affichée remplit la frise.
  const doneSteps = outcome && step === "decision" ? STEPS.length : index + 1;
  const identified = identification?.status === "verifiee";

  return (
    <div className="flex min-h-dvh flex-col bg-bg text-fg">
      <TopBar runtime={runtime} sun={sun} onToggleSun={toggleSun} helpOn={help !== null && !help.off} onToggleHelp={() => help && setHelp(help.off ? enableHelp(help) : disableHelp(help))} />
      <NetworkBanner runtime={runtime} identified={identified} />
      <Progress done={doneSteps} wide={step === "decision"} />
      <div className="c-steprow" data-wide={step === "decision" || undefined}>
        <StepHeader n={index + 1} name={step} />
        {runtime.online ? (
          <Pill tone="ok" icon="pulse">
            {t("net.online")}
          </Pill>
        ) : (
          <Pill tone="warn" icon="wifiOff">
            {t("net.offline.short")}
          </Pill>
        )}
      </div>
      {flash ? (
        <div className="flash">
          <Notice tone={flash.tone} role={flash.tone === "ok" ? "status" : "alert"} testId="flash" code={flash.message.code}>
            <span>{flash.message.text}</span>
            {flash.message.detail ? <span className="detail">{flash.message.detail}</span> : null}
          </Notice>
        </div>
      ) : null}
      <MeasureConsent />
      {help && shouldShowHelp(help, step) ? <CoachMark step={step} onGotIt={() => gotIt(help, step)} onDisable={() => setHelp(disableHelp(help))} /> : null}
      {step === "card" ? <CardScreen busy={busy} onLookup={(member_number) => startIdentification({ member_number })} onScanned={(qr_payload) => startIdentification({ qr_payload })} extra={<MeasureSwitchRow />} /> : null}
      {step === "identity" && identification ? <IdentityScreen identification={identification} busy={busy} onConfirm={confirmIdentity} /> : null}
      {step === "code" && identification ? (
        <CodeScreen
          displayName={identification.beneficiary.display_name}
          busy={busy}
          onValidate={verifyCode}
          onResend={resendCode}
          onIncomplete={() => setFlash({ tone: "crit", message: { text: t("code.incomplete") } })}
        />
      ) : null}
      {step === "acts" ? (
        <ActsScreen
          tariff={tariff}
          selected={selected}
          busy={busy}
          loading={runtime.policyLoading}
          {...(runtime.online ? { onRetryTariff: runtime.retryPolicy } : {})}
          onToggle={toggleAct}
          onSubmit={submitActs}
        />
      ) : null}
      {step === "decision" && outcome ? (
        <DecisionScreen
          outcome={outcome}
          record={outcome.kind === "provisional" ? recordFor(runtime.queue, outcome.offlineRef) : undefined}
          thresholdXof={runtime.policy?.threshold_xof ?? null}
          timeZone={runtime.timeZone}
          beneficiary={identification?.beneficiary}
          acts={tariff.filter((item) => selected.includes(item.act_code))}
          busy={busy}
          onNext={nextPatient}
          onRetry={submitActs}
          onEditActs={() => {
            setOutcome(null);
            go("acts");
          }}
        />
      ) : null}
    </div>
  );
}
