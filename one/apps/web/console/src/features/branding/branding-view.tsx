"use client";

import { AlertTriangleIcon, CheckIcon, Loader2Icon, RotateCcwIcon, WandIcon, XIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent } from "react";
import { ApiError } from "@/api/client";
import { useBrandingSettings, useUpdateBranding, useVerifyBrandingDomain } from "@/api/queries";
import type { BrandingSettings, Problem } from "@/api/types";
import { FormField, INPUT_CLASS, TEXTAREA_CLASS } from "@/components/form-field";
import { RequireRole } from "@/components/require-role";
import { ErrorState, LoadingRows, PageHeader, Panel } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { t, tDynamic, type MessageKey } from "@/i18n";
import {
  OVERRIDABLE_TOKENS,
  THEMES,
  colorField,
  contrastReport,
  draftErrors,
  draftFromSettings,
  effectiveColor,
  previewVariables,
  problemFieldErrors,
  readLogoFile,
  requestFromDraft,
  suggestionFor,
  type BrandingDraft,
  type OverridableToken,
  type ThemeName,
} from "./branding-model";

/** Titre clair de chaque refus de marque (BRD-01 à BRD-06) ; le détail vient de l'API. */
const BRAND_ERROR_TITLES: Partial<Record<string, MessageKey>> = {
  "BRD-01": "branding.contrastRefused",
  "BRD-02": "branding.errorTitles.BRD-02",
  "BRD-03": "branding.errorTitles.BRD-03",
  "BRD-04": "branding.errorTitles.BRD-04",
  "BRD-05": "branding.errorTitles.BRD-05",
  "BRD-06": "branding.errorTitles.BRD-06",
};

const ratioFormat = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const limitFormat = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

export function BrandingView() {
  return (
    <RequireRole roles={["admin"]} message="forbidden.adminOnly">
      <BrandingContent />
    </RequireRole>
  );
}

/**
 * Marque de l'organisation (P3, `getBrandingSettings` / `updateBrandingSettings`) : nom, logo,
 * jetons de la LISTE FERMÉE en clair et en sombre, domaine et mentions. Aperçu en direct, contraste
 * recalculé à chaque saisie (même calcul que l'API), refus de l'API (BRD-01 à 04) rattachés à leur
 * champ, avec la couleur conforme la plus proche quand elle se calcule.
 */
function BrandingContent() {
  const settings = useBrandingSettings();
  if (settings.isPending) return <LoadingRows rows={6} />;
  if (settings.isError) return <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />;
  // Pas de clé sur la date de mise à jour : l'enregistrement ne remonte pas le formulaire (message gardé).
  return <BrandingForm settings={settings.data} />;
}

function BrandingForm({ settings }: { settings: BrandingSettings }) {
  const [draft, setDraft] = useState<BrandingDraft>(() => draftFromSettings(settings));
  const [submitted, setSubmitted] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);
  const update = useUpdateBranding();
  const alertRef = useRef<HTMLDivElement>(null);
  const localErrors = draftErrors(draft);
  const apiProblem: Problem | null = update.error instanceof ApiError ? update.error.problem : null;
  const apiErrors = problemFieldErrors(apiProblem);

  const blocked = submitted && Object.keys(localErrors).length > 0;
  // Le message d'échec prend le focus au moment où il apparaît (lecteur d'écran, clavier).
  useEffect(() => {
    if (update.isError || blocked) alertRef.current?.focus();
  }, [update.isError, blocked]);

  const edit = (change: Partial<BrandingDraft>) => {
    setDraft((d) => ({ ...d, ...change }));
    setSubmitted(false);
    if (update.isError || update.isSuccess) update.reset();
  };
  const setColor = (theme: ThemeName, token: OverridableToken, value: string) =>
    edit({ colors: { ...draft.colors, [theme]: { ...draft.colors[theme], [token]: value } } });

  const fieldError = (field: string, local?: string | null) => (submitted && local ? local : null) ?? apiErrors[field]?.join(" ") ?? null;
  const localMessage = (field: string) => {
    const key = localErrors[field];
    return key ? t(`branding.errors.${key}`) : null;
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSubmitted(true);
    if (Object.keys(localErrors).length > 0) return;
    update.mutate(requestFromDraft(draft));
  };

  return (
    <>
      <PageHeader eyebrow={t("branding.eyebrow")} title={t("branding.title")}>
        <p className="m-0 max-w-[80ch] text-fg-2">{t("branding.intro")}</p>
      </PageHeader>
      <form noValidate onSubmit={submit} className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="flex min-w-0 flex-col gap-5">
          {blocked ? (
            <div ref={alertRef} tabIndex={-1} role="alert" className="flex flex-col gap-1 rounded-md border border-crit bg-crit-bg p-4 text-crit" data-testid="branding-local-errors">
              <p className="font-semibold">{t("branding.localErrorsTitle")}</p>
              <p>{t("branding.localErrorsBody")}</p>
            </div>
          ) : null}
          {update.isError ? (
            <div ref={alertRef} tabIndex={-1} role="alert" className="flex flex-col gap-1.5 rounded-md border border-crit bg-crit-bg p-4 text-crit" data-testid="branding-api-error" data-code={apiProblem?.code}>
              <p className="flex items-center gap-2 font-semibold">
                <AlertTriangleIcon className="size-4" aria-hidden />
                {apiProblem && apiProblem.code in BRAND_ERROR_TITLES ? t(BRAND_ERROR_TITLES[apiProblem.code]!) : (apiProblem?.message ?? t("states.unknownError"))}
              </p>
              {apiProblem && apiProblem.code in BRAND_ERROR_TITLES ? <p>{apiProblem.message}</p> : null}
              <p>{apiProblem?.action ?? t("states.unknownAction")}</p>
              {apiProblem ? <p className="tabular text-caption">{t("branding.code", { code: apiProblem.code })}</p> : null}
            </div>
          ) : null}
          {update.isSuccess ? (
            <div role="status" className="flex items-start gap-2 rounded-md border border-line bg-ok-bg p-4 text-ok" data-testid="branding-saved">
              <CheckIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
              <div>
                <p className="font-semibold">{t("branding.savedTitle")}</p>
                <p>{t("branding.savedBody")}</p>
              </div>
            </div>
          ) : null}

          <Panel className="flex flex-col gap-4 p-5" aria-labelledby="branding-identity">
            <h2 id="branding-identity" className="text-title font-semibold">
              {t("branding.identityTitle")}
            </h2>
            <FormField id="display_name" label={t("branding.displayName")} hint={t("branding.displayNameHint")} error={fieldError("display_name", localMessage("display_name"))}>
              {(props) => <input {...props} className={INPUT_CLASS} value={draft.displayName} maxLength={80} required onChange={(e) => edit({ displayName: e.target.value })} />}
            </FormField>
            <FormField id="logo" label={t("branding.logo")} hint={t("branding.logoHint")} error={logoError ?? fieldError("logo")}>
              {(props) => (
                <div className="flex flex-wrap items-center gap-3">
                  {draft.logo ? <img src={draft.logo.src} alt={t("branding.logoCurrent")} width={40} height={40} className="size-10 rounded-md border border-line object-contain" data-testid="branding-logo-preview" /> : null}
                  <input
                    {...props}
                    type="file"
                    accept="image/png,image/webp,image/jpeg,image/svg+xml"
                    className="peer sr-only"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const read = await readLogoFile(file);
                      if (read.ok) {
                        setLogoError(null);
                        edit({ logo: read.logo });
                      } else setLogoError(t(`branding.logoErrors.${read.reason}`));
                    }}
                  />
                  {/* Bouton en français (le texte natif du sélecteur de fichier suit la langue du navigateur). */}
                  <label
                    htmlFor={props.id}
                    className="inline-flex h-10 cursor-pointer items-center rounded-btn border border-line-2 bg-surface px-3 text-dense font-medium text-fg hover:bg-sunk peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[var(--focus)] peer-focus-visible:outline-solid"
                  >
                    {t(draft.logo ? "branding.logoReplace" : "branding.logoChoose")}
                  </label>
                  {draft.logo ? (
                    <Button variant="outline" className="h-10" onClick={() => edit({ logo: null })}>
                      <XIcon aria-hidden />
                      {t("branding.logoRemove")}
                    </Button>
                  ) : null}
                </div>
              )}
            </FormField>
          </Panel>

          {THEMES.map((theme) => (
            <ThemeColors key={theme} theme={theme} draft={draft} setColor={setColor} fieldError={(field) => fieldError(field, localMessage(field))} />
          ))}

          <Panel className="flex flex-col gap-4 p-5" aria-labelledby="branding-domain">
            <h2 id="branding-domain" className="text-title font-semibold">
              {t("branding.domainTitle")}
            </h2>
            <FormField id="custom_domain" label={t("branding.customDomain")} hint={t("branding.customDomainHint")} error={fieldError("custom_domain", localMessage("custom_domain"))}>
              {(props) => <input {...props} className={INPUT_CLASS} value={draft.customDomain} inputMode="url" autoComplete="off" spellCheck={false} onChange={(e) => edit({ customDomain: e.target.value.toLowerCase() })} />}
            </FormField>
            <DomainProof settings={settings} draftDomain={draft.customDomain.trim()} />
            <FormField id="legal_notice" label={t("branding.legalNotice")} hint={t("branding.noticeHint")} error={fieldError("legal_notice", localMessage("legal_notice"))}>
              {(props) => <textarea {...props} className={TEXTAREA_CLASS} value={draft.legalNotice} maxLength={4000} onChange={(e) => edit({ legalNotice: e.target.value })} />}
            </FormField>
            <FormField id="privacy_notice" label={t("branding.privacyNotice")} hint={t("branding.noticeHint")} error={fieldError("privacy_notice", localMessage("privacy_notice"))}>
              {(props) => <textarea {...props} className={TEXTAREA_CLASS} value={draft.privacyNotice} maxLength={4000} onChange={(e) => edit({ privacyNotice: e.target.value })} />}
            </FormField>
          </Panel>

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" className="h-10 px-4 text-dense" disabled={update.isPending} aria-busy={update.isPending || undefined}>
              {update.isPending ? <Loader2Icon className="motion-safe:animate-spin" aria-hidden /> : null}
              {t("branding.submit")}
            </Button>
            <Button variant="outline" className="h-10 px-4 text-dense" onClick={() => edit(draftFromSettings(settings))}>
              <RotateCcwIcon aria-hidden />
              {t("branding.reset")}
            </Button>
          </div>
        </div>
        <LivePreview draft={draft} />
      </form>
    </>
  );
}

/**
 * Preuve de propriété du domaine (CR-P3-02, `verifyBrandingDomain`) : un domaine déclaré n'est
 * servi qu'une fois prouvé par un enregistrement DNS TXT. Statut en mots (en attente = info,
 * vérifié = ok), enregistrement à publier, bouton « Vérifier le domaine », refus BRD-05 / BRD-06.
 */
function DomainProof({ settings, draftDomain }: { settings: BrandingSettings; draftDomain: string }) {
  const verify = useVerifyBrandingDomain();
  const problem = verify.error instanceof ApiError ? verify.error.problem : null;
  if (!settings.custom_domain) return null;
  if (draftDomain !== settings.custom_domain) {
    return <p className="text-caption text-fg-2" data-testid="domain-unsaved">{t("branding.domainUnsaved")}</p>;
  }
  const verified = settings.custom_domain_status === "verifie";
  const record = settings.custom_domain_verification;
  return (
    <div className="flex flex-col gap-3 rounded-md border border-line p-4" data-testid="domain-proof" data-status={settings.custom_domain_status ?? undefined}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{t("branding.domainStatus", { domain: settings.custom_domain })}</span>
        <Badge tone={verified ? "ok" : "info"} dot={false}>
          {verified ? <CheckIcon aria-hidden /> : <Loader2Icon aria-hidden />}
          {t(verified ? "branding.domainVerified" : "branding.domainPending")}
        </Badge>
      </div>
      {!verified && record ? (
        <>
          <p className="text-fg-2">{t("branding.domainHowTo")}</p>
          <dl className="grid grid-cols-1 gap-x-4 gap-y-1 text-dense md:grid-cols-[auto_minmax(0,1fr)]">
            <dt className="text-fg-2">{t("branding.recordType")}</dt>
            <dd className="tabular m-0">{record.record_type}</dd>
            <dt className="text-fg-2">{t("branding.recordName")}</dt>
            <dd className="tabular m-0 break-all" data-testid="dns-record-name">{record.record_name}</dd>
            <dt className="text-fg-2">{t("branding.recordValue")}</dt>
            <dd className="tabular m-0 break-all" data-testid="dns-record-value">{record.record_value}</dd>
          </dl>
          <Button variant="outline" className="h-10 self-start px-4 text-dense" onClick={() => verify.mutate()} disabled={verify.isPending} aria-busy={verify.isPending || undefined}>
            {verify.isPending ? <Loader2Icon className="motion-safe:animate-spin" aria-hidden /> : null}
            {t("branding.domainVerify")}
          </Button>
        </>
      ) : null}
      {verify.isError ? (
        <div role="alert" className="flex flex-col gap-1 rounded-md bg-crit-bg p-3 text-crit" data-testid="domain-error" data-code={problem?.code}>
          <p className="font-semibold">{problem && problem.code in BRAND_ERROR_TITLES ? t(BRAND_ERROR_TITLES[problem.code]!) : (problem?.message ?? t("states.unknownError"))}</p>
          {problem && problem.code in BRAND_ERROR_TITLES ? <p>{problem.message}</p> : null}
          <p>{problem?.action ?? t("states.unknownAction")}</p>
          {problem ? <p className="tabular text-caption">{t("branding.code", { code: problem.code })}</p> : null}
        </div>
      ) : null}
      {verify.isSuccess ? (
        <p role="status" className="flex items-center gap-1.5 text-ok" data-testid="domain-verified">
          <CheckIcon className="size-4" aria-hidden />
          {t("branding.domainVerifiedNow")}
        </p>
      ) : null}
    </div>
  );
}

function ThemeColors({
  theme,
  draft,
  setColor,
  fieldError,
}: {
  theme: ThemeName;
  draft: BrandingDraft;
  setColor: (theme: ThemeName, token: OverridableToken, value: string) => void;
  fieldError: (field: string) => string | null;
}) {
  const report = useMemo(() => contrastReport(draft, theme), [draft, theme]);
  const headingId = `branding-colors-${theme}`;
  return (
    <Panel className="flex flex-col gap-4 p-5" aria-labelledby={headingId} data-testid={`colors-${theme}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={headingId} className="text-title font-semibold">
          {tDynamic("branding.themeTitle", theme)}
        </h2>
        {report.problems.length === 0 ? (
          <Badge tone="ok" dot={false} data-testid={`contrast-${theme}`}>
            <CheckIcon aria-hidden />
            {t("branding.contrastOk")}
          </Badge>
        ) : (
          <Badge tone="crit" dot={false} data-testid={`contrast-${theme}`}>
            <AlertTriangleIcon aria-hidden />
            {t("branding.contrastKo", { count: report.pairs.filter((p) => !p.ok).length })}
          </Badge>
        )}
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {OVERRIDABLE_TOKENS.map((token) => {
          const field = colorField(theme, token);
          const id = `${theme}-${token}`;
          const live = report.problems.some((p) => p.token === token);
          const suggestion = live || fieldError(field) ? suggestionFor(draft, theme, token) : null;
          const error = fieldError(field) ?? (live ? t("branding.liveContrast") : null);
          return (
            <FormField key={token} id={id} label={tDynamic("branding.token", token)} hint={t("branding.colorHint")} error={error}>
              {(props) => (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      aria-label={t("branding.colorPicker", { token: tDynamic("branding.token", token), theme: tDynamic("branding.themeName", theme) })}
                      value={effectiveColor(draft, theme, token)}
                      onChange={(e) => setColor(theme, token, e.target.value)}
                      className="h-10 w-12 shrink-0 cursor-pointer rounded-md border border-line-2 bg-surface p-1"
                    />
                    <input
                      {...props}
                      className={`${INPUT_CLASS} tabular`}
                      value={draft.colors[theme][token]}
                      placeholder={effectiveColor({ ...draft, colors: { ...draft.colors, [theme]: { ...draft.colors[theme], [token]: "" } } }, theme, token)}
                      maxLength={7}
                      spellCheck={false}
                      autoComplete="off"
                      onChange={(e) => setColor(theme, token, e.target.value.trim())}
                    />
                    {draft.colors[theme][token] ? (
                      <Button variant="ghost" className="h-10" onClick={() => setColor(theme, token, "")} aria-label={t("branding.colorDefaultFor", { token: tDynamic("branding.token", token) })}>
                        {t("branding.colorDefault")}
                      </Button>
                    ) : null}
                  </div>
                  {suggestion ? (
                    <Button variant="outline" className="h-10 self-start" onClick={() => setColor(theme, token, suggestion)} data-testid={`suggest-${id}`}>
                      <WandIcon aria-hidden />
                      {t("branding.useSuggestion", { color: suggestion })}
                    </Button>
                  ) : null}
                </div>
              )}
            </FormField>
          );
        })}
      </div>
      <details className="rounded-md border border-line p-3">
        <summary className="flex min-h-8 cursor-pointer items-center font-medium">{t("branding.pairsTitle")}</summary>
        <table className="mt-2 w-full text-dense" aria-label={t("branding.pairsLabel", { theme: tDynamic("branding.themeName", theme) })}>
          <thead>
            <tr className="text-left text-fg-2">
              <th scope="col" className="py-1 font-medium">
                {t("branding.pairCol")}
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                {t("branding.ratioCol")}
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                {t("branding.statusCol")}
              </th>
            </tr>
          </thead>
          <tbody>
            {report.pairs.map((p) => (
              <tr key={`${p.pair[0]}-${p.pair[1]}`} className="border-t border-line">
                <td className="py-1.5">{t("branding.pair", { fg: tDynamic("branding.cssToken", p.pair[0].slice(2)), bg: tDynamic("branding.cssToken", p.pair[1].slice(2)) })}</td>
                <td className="tabular py-1.5 text-right">{t("branding.ratio", { ratio: ratioFormat.format(p.ratio), min: limitFormat.format(p.minimum) })}</td>
                <td className="py-1.5 text-right">
                  <Badge tone={p.ok ? "ok" : "crit"} dot={false}>
                    {p.ok ? <CheckIcon aria-hidden /> : <XIcon aria-hidden />}
                    {t(p.ok ? "branding.pairOk" : "branding.pairKo")}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </Panel>
  );
}

/**
 * Aperçu en direct, clair et sombre : un extrait de console aux couleurs saisies (variables CSS
 * posées sur le cadre ; aucune couleur écrite dans le code). Décoratif : la conformité est dite en
 * texte dans chaque thème, l'aperçu montre aussi une couleur refusée, telle qu'elle serait vue.
 */
function LivePreview({ draft }: { draft: BrandingDraft }) {
  return (
    <aside className="flex flex-col gap-3 xl:sticky xl:top-20" aria-labelledby="branding-preview">
      <h2 id="branding-preview" className="text-title font-semibold">
        {t("branding.previewTitle")}
      </h2>
      <p className="text-caption text-fg-2">{t("branding.previewHint")}</p>
      {THEMES.map((theme) => (
        <figure key={theme} className="m-0 flex flex-col gap-1.5">
          <figcaption className="text-caption font-medium text-fg-2">{tDynamic("branding.themeName", theme)}</figcaption>
          <div aria-hidden="true" data-testid={`brand-preview-${theme}`} style={previewVariables(draft, theme) as CSSProperties} className="flex flex-col gap-3 rounded-lg border border-line bg-bg p-3 text-fg">
            <div className="flex items-center gap-2 rounded-md bg-surface p-2">
              {draft.logo ? (
                <img src={draft.logo.src} alt="" width={24} height={24} className="size-6 rounded-sm object-contain" />
              ) : (
                <span className="grid size-6 place-items-center rounded-sm bg-brand text-caption font-bold text-brand-fg">{draft.displayName.trim().charAt(0).toLocaleUpperCase("fr") || t("app.monogram")}</span>
              )}
              <span className="truncate text-dense font-semibold">{draft.displayName.trim() || t("app.name")}</span>
            </div>
            <div className="flex flex-col gap-1 rounded-md bg-surface p-2 text-dense">
              <span className="rounded-sm bg-brand-soft px-2 py-1 font-medium text-brand">{t("branding.previewNavActive")}</span>
              <span className="px-2 py-1 text-fg-2">{t("branding.previewNav")}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2 rounded-md bg-surface p-2">
              <span className="rounded-btn bg-brand px-3 py-1.5 text-dense font-medium text-brand-fg">{t("branding.previewButton")}</span>
              <span className="text-dense text-brand underline">{t("branding.previewLink")}</span>
              <span className="rounded-btn border border-line-2 px-3 py-1.5 text-dense outline-2 outline-offset-2 outline-[var(--focus)] outline-solid">{t("branding.previewFocus")}</span>
            </div>
            <div className="rounded-md bg-brand-deep p-3 text-brand-on-deep">
              <p className="m-0 text-dense font-semibold">{t("branding.previewCard")}</p>
              <p className="m-0 text-caption text-[var(--brand-on-deep-2)]">{t("branding.previewCardSub")}</p>
            </div>
            <span className="self-start rounded-full bg-ok-bg px-2 py-0.5 text-caption font-medium text-ok">{t("branding.previewStatus")}</span>
          </div>
        </figure>
      ))}
    </aside>
  );
}
