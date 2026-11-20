"use client";

import Link from "next/link";
import { toUiError } from "@/api/errors";
import { t, tp, type MessageKey } from "@/i18n";
import { measureOffForInstance } from "@/lib/measure-consent";
import { track } from "@/lib/track";
import { useMeasureChoice } from "@/member/useMeasureChoice";
import { useOnline } from "@/member/queries";
import { EmptyState, ErrorState, LoadingState } from "@/ui/states";
import { TONE_CLASS, type StatusLook } from "@/ui/tones";
import { Button, Icon, Notice, Pill, ScreenTitle, type IconName } from "@/ui/ui";
import { LEAD_DAYS, type AppNotification, type LeadDays, type NotificationKind, type NotificationPrefs } from "./derive";
import { useNotifications } from "./useNotifications";

const NEW_LOOK: StatusLook = { tone: "info", icon: "info", label: "notif.new" };

const KIND_ICON: Record<NotificationKind, IconName> = {
  "contribution-late": "wallet",
  "contribution-due": "wallet",
  "claim-progress": "clip",
  "claim-new": "clip",
  "card-blocked": "lock",
  "card-expired": "card",
  "card-expiring": "card",
};

/** Titre et texte d'une notification, depuis les fichiers de traduction (jamais en dur). */
export function notificationText(n: AppNotification): { title: string; text: string } {
  const params = { ...n.params };
  if (typeof params.status === "string") params.status = t(`claim.status.${params.status}` as MessageKey);
  const title = t(`notif.${n.kind}.title` as MessageKey, params);
  if (n.kind === "contribution-due") {
    const days = Number(n.params.days);
    return { title, text: days === 0 ? t("notif.contribution-due.today", params) : tp("notif.contribution-due.text", days, params) };
  }
  return { title, text: t(`notif.${n.kind}.text` as MessageKey, params) };
}

function NotificationItem({ n, onOpen }: { n: AppNotification; onOpen: () => void }) {
  const { title, text } = notificationText(n);
  return (
    <li data-testid="notification" data-kind={n.kind} data-tone={n.tone} data-unread={n.unread || undefined}>
      <Link
        className="notif-row"
        href={n.href}
        onClick={() => {
          onOpen();
          track("notification_opened", { variant: "in_app" });
        }}
      >
        <span className={`notif-ic ${TONE_CLASS[n.tone]}`} aria-hidden="true">
          <Icon name={KIND_ICON[n.kind]} />
        </span>
        <span className="row-main">
          <b>{title}</b>
          <span>{text}</span>
          {n.unread ? <Pill look={NEW_LOOK} /> : null}
        </span>
        <Icon name="chev" />
      </Link>
    </li>
  );
}

const PREF_ROWS: { key: "contributions" | "claims" | "cards"; label: MessageKey }[] = [
  { key: "contributions", label: "notif.prefs.contributions" },
  { key: "claims", label: "notif.prefs.claims" },
  { key: "cards", label: "notif.prefs.cards" },
];

/**
 * Interrupteur de la mesure d'usage pseudonyme (choix gardé sur le téléphone, même après la
 * déconnexion). Éteint tant qu'aucun choix ; allumer vaut accord, éteindre vaut refus.
 */
function MeasureSwitch() {
  const [choice, setChoice] = useMeasureChoice();
  if (choice === undefined || measureOffForInstance()) return null;
  const on = choice === "granted";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-describedby="measure-hint"
      className="switch-row"
      data-testid="pref-measure"
      onClick={() => setChoice(on ? "refused" : "granted")}
    >
      <span className="switch-label">{t("notif.prefs.measure")}</span>
      <span className="switch-state" aria-hidden="true">
        {t(on ? "notif.prefs.on" : "notif.prefs.off")}
      </span>
      <span className="switch" aria-hidden="true">
        <i />
      </span>
    </button>
  );
}

function Preferences({ prefs, onChange }: { prefs: NotificationPrefs; onChange: (prefs: NotificationPrefs) => void }) {
  return (
    <details className="panel prefs" data-testid="notification-prefs">
      <summary className="panel-h prefs-sum">
        <h2 className="panel-t" id="prefs-t">
          {t("notif.prefs.title")}
        </h2>
        <Icon name="chev" />
      </summary>
      <div className="pad stack">
        <p>{t("notif.prefs.lead")}</p>
        {PREF_ROWS.map((row) => {
          const on = prefs[row.key];
          return (
            <button key={row.key} type="button" role="switch" aria-checked={on} className="switch-row" data-testid={`pref-${row.key}`} onClick={() => onChange({ ...prefs, [row.key]: !on })}>
              <span className="switch-label">{t(row.label)}</span>
              <span className="switch-state" aria-hidden="true">
                {t(on ? "notif.prefs.on" : "notif.prefs.off")}
              </span>
              <span className="switch" aria-hidden="true">
                <i />
              </span>
            </button>
          );
        })}
        <div className="field-group">
          <label className="field-label" htmlFor="lead-days">
            {t("notif.prefs.leadDays")}
          </label>
          <select
            id="lead-days"
            className="field"
            value={prefs.leadDays}
            onChange={(event) => onChange({ ...prefs, leadDays: Number(event.target.value) as LeadDays })}
          >
            {LEAD_DAYS.map((days) => (
              <option key={days} value={days}>
                {t("notif.prefs.leadDays.option", { count: days })}
              </option>
            ))}
          </select>
        </div>
        <MeasureSwitch />
        <p id="measure-hint">{t("notif.prefs.measureHint")}</p>
      </div>
    </details>
  );
}

/**
 * Mes notifications (Phase 2, voie A) : échéance de cotisation proche ou dépassée, remboursement
 * passé à l'étape suivante, carte bloquée ou couverture terminée. Dérivées des données du contrat,
 * calculées sur le téléphone ; rien n'est envoyé (ni SMS, ni WhatsApp). Préférences locales.
 */
export function NotificationsScreen() {
  const view = useNotifications();
  const online = useOnline();

  return (
    <div className="m-body m-single" data-testid="notifications-screen">
      <div className="m-col">
        <p className="eyebrow">{t("notif.eyebrow")}</p>
        <ScreenTitle>{t("notif.title")}</ScreenTitle>
        <p>{t("notif.lead")}</p>

        {!online && view.ready ? (
          <Notice tone="warn" icon="wifiOff" testId="notifications-offline">
            <p>{t("notif.offline")}</p>
          </Notice>
        ) : null}
        {view.pending ? <LoadingState label={t("loading.notifications")} rows={3} /> : null}
        {view.failed ? (
          <ErrorState title={t("error.title.notifications")} error={view.firstError} onRetry={view.retry} retrying={view.retrying} testId="notifications-error" />
        ) : null}
        {view.partialError ? (
          <Notice tone="warn" testId="notifications-partial" code={toUiError(view.partialError).code}>
            <p>{t("notif.partial")}</p>
          </Notice>
        ) : null}

        {view.ready && view.list.length === 0 ? <EmptyState title={t("notif.empty.title")}>{t("notif.empty.text")}</EmptyState> : null}
        {view.list.length > 0 ? (
          <>
            <ul className="panel rows" aria-label={t("notif.listLabel")} data-testid="notifications">
              {view.list.map((n) => (
                <NotificationItem key={n.key} n={n} onOpen={() => view.markRead(n.key)} />
              ))}
            </ul>
            {view.unread > 0 ? (
              <Button variant="secondary" icon="check" className="btn-block" onClick={view.markAllRead}>
                {t("notif.markAll")}
              </Button>
            ) : (
              <p role="status" className="notif-allread">
                {t("notif.allRead")}
              </p>
            )}
          </>
        ) : null}
      </div>
      <div className="m-col">
        <Preferences prefs={view.state.prefs} onChange={(prefs) => view.setState({ ...view.state, prefs })} />
      </div>
    </div>
  );
}

/** La cloche de la barre du haut est dans `./NotificationBell.tsx` (compteur chargé à part). */
