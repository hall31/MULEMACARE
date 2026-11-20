"use client";

import { AlertTriangleIcon, CheckIcon, Loader2Icon, PlusIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ApiError } from "@/api/client";
import { useConfigurationTemplates, useCreateConfigurationTemplate, useCreateOrganization } from "@/api/queries";
import type { ConfigurationTemplate, CountryCode, OrganizationCapability, OrganizationOnboarding, Problem } from "@/api/types";
import { FormField, INPUT_CLASS } from "@/components/form-field";
import { RequireRole } from "@/components/require-role";
import { EmptyState, ErrorState, LoadingRows, PageHeader, Panel } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { t, tDynamic } from "@/i18n";
import { formatDate } from "@/lib/format";
import { EMPTY_ORGANIZATION, organizationErrors, organizationRequest, problemErrors, templateChoices, type OrganizationDraft } from "./organization-model";

export function OrganizationsView() {
  return (
    <RequireRole roles={["admin_plateforme"]} message="forbidden.platformOnly">
      <OrganizationsContent />
    </RequireRole>
  );
}

const COUNTRIES: CountryCode[] = ["CI", "SN"];
const CAPABILITIES: OrganizationCapability[] = ["porteur_de_risque", "gestionnaire", "distributeur"];

/**
 * Accueil d'organisation (P3, `createOrganization`, `listConfigurationTemplates`,
 * `createConfigurationTemplate`), réservé à l'administrateur de plateforme : formulaire validé
 * avant envoi, erreurs ORG-01 (identifiant pris) et ORG-02 (gabarit) sous leur champ, preuve de
 * l'accueil (gabarit copié, statut « intégration »), gabarits publiés.
 */
function OrganizationsContent() {
  const [onboarded, setOnboarded] = useState<OrganizationOnboarding[]>([]);
  const templates = useConfigurationTemplates();
  return (
    <>
      <PageHeader eyebrow={t("organizations.eyebrow")} title={t("organizations.title")}>
        <p className="m-0 max-w-[80ch] text-fg-2">{t("organizations.intro")}</p>
      </PageHeader>
      <div className="grid grid-cols-1 items-start gap-5 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <CreateOrganization templates={templates.data?.items ?? []} templatesLoading={templates.isPending} onCreated={(o) => setOnboarded((list) => [o, ...list])} />
        <div className="flex min-w-0 flex-col gap-5">
          <OnboardedList items={onboarded} />
          <Panel aria-labelledby="templates-title">
            <div className="flex flex-col gap-1 border-b border-line p-4">
              <h2 id="templates-title" className="text-title font-semibold">
                {t("organizations.templatesTitle")}
              </h2>
              <p className="text-fg-2">{t("organizations.templatesIntro")}</p>
            </div>
            {templates.isPending ? <LoadingRows rows={3} /> : null}
            {templates.isError ? (
              <div className="p-4">
                <ErrorState error={templates.error} onRetry={() => void templates.refetch()} />
              </div>
            ) : null}
            {templates.data && templates.data.items.length === 0 ? <EmptyState title={t("organizations.templatesEmptyTitle")} body={t("organizations.templatesEmptyBody")} /> : null}
            {templates.data && templates.data.items.length > 0 ? <TemplatesTable items={templates.data.items} /> : null}
            <PublishTemplate />
          </Panel>
        </div>
      </div>
    </>
  );
}

function CreateOrganization({ templates, templatesLoading, onCreated }: { templates: ConfigurationTemplate[]; templatesLoading: boolean; onCreated: (o: OrganizationOnboarding) => void }) {
  const [draft, setDraft] = useState<OrganizationDraft>(EMPTY_ORGANIZATION);
  const [submitted, setSubmitted] = useState(false);
  const [done, setDone] = useState<OrganizationOnboarding | null>(null);
  const create = useCreateOrganization();
  const summaryRef = useRef<HTMLDivElement>(null);
  const successRef = useRef<HTMLDivElement>(null);
  const choices = useMemo(() => templateChoices(templates, draft.country), [templates, draft.country]);
  const localErrors = organizationErrors(draft, choices);
  const problem: Problem | null = create.error instanceof ApiError ? create.error.problem : null;
  const apiErrors = problemErrors(problem);
  const blocked = submitted && Object.keys(localErrors).length > 0;

  useEffect(() => {
    if (create.isError || blocked) summaryRef.current?.focus();
  }, [create.isError, blocked]);
  useEffect(() => {
    if (done) successRef.current?.focus();
  }, [done]);
  // Gabarit par défaut : la dernière version du premier gabarit du pays choisi.
  useEffect(() => {
    if (!choices.some((c) => c.value === draft.template)) setDraft((d) => ({ ...d, template: choices[0]?.value ?? "" }));
  }, [choices, draft.template]);

  const edit = (change: Partial<OrganizationDraft>) => {
    setDraft((d) => ({ ...d, ...change }));
    if (create.isError) create.reset();
  };
  const errorOf = (field: string) => (submitted && localErrors[field] ? t(`organizations.errors.${localErrors[field]}`) : null) ?? apiErrors[field] ?? null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSubmitted(true);
    if (Object.keys(localErrors).length > 0) return;
    create.mutate(organizationRequest(draft), {
      onSuccess: (result) => {
        onCreated(result);
        setDone(result);
      },
    });
  };

  if (done) {
    const c = done.copied;
    return (
      <Panel className="flex flex-col gap-3 p-5" aria-labelledby="onboarded-title">
        <div ref={successRef} tabIndex={-1} role="status" className="flex items-start gap-3 outline-none" data-testid="organization-created">
          <span aria-hidden className="grid size-10 shrink-0 place-items-center rounded-full border-2 border-ok text-ok">
            <CheckIcon className="size-5" />
          </span>
          <div className="flex flex-col gap-1">
            <h2 id="onboarded-title" className="text-title font-semibold">
              {t("organizations.createdTitle", { name: done.organization.name })}
            </h2>
            <p>{t("organizations.createdProof", { slug: done.organization.slug, code: done.template.code, version: done.template.version })}</p>
            <p>{t("organizations.createdCopied", { accounts: c.ledger_accounts, rules: c.rules, plans: c.plans, coverages: c.coverages, acts: c.acts, tariffs: c.tariff_items })}</p>
            <p>{t("organizations.createdManager", { name: done.first_manager.display_name, roles: done.first_manager.roles.map((r) => tDynamic("roles", r.role)).join(", ") })}</p>
            <p className="text-fg-2">{t("organizations.createdNext")}</p>
          </div>
        </div>
        <Button
          variant="outline"
          className="h-10 self-start px-4 text-dense"
          onClick={() => {
            setDone(null);
            setDraft(EMPTY_ORGANIZATION);
            setSubmitted(false);
            create.reset();
          }}
        >
          <PlusIcon aria-hidden />
          {t("organizations.another")}
        </Button>
      </Panel>
    );
  }

  const selected = choices.find((c) => c.value === draft.template)?.template;
  return (
    <Panel aria-labelledby="create-title">
      <form noValidate onSubmit={submit} className="flex flex-col gap-4 p-5">
        <h2 id="create-title" className="text-title font-semibold">
          {t("organizations.createTitle")}
        </h2>
        {blocked || create.isError ? (
          <div ref={summaryRef} tabIndex={-1} role="alert" className="flex flex-col gap-1 rounded-md border border-crit bg-crit-bg p-4 text-crit" data-testid="organization-error" data-code={problem?.code}>
            <p className="flex items-center gap-2 font-semibold">
              <AlertTriangleIcon className="size-4" aria-hidden />
              {blocked ? t("organizations.localErrorsTitle") : (problem?.message ?? t("states.unknownError"))}
            </p>
            <p>{blocked ? t("organizations.localErrorsBody") : (problem?.action ?? t("states.unknownAction"))}</p>
            {!blocked && problem ? <p className="tabular text-caption">{t("branding.code", { code: problem.code })}</p> : null}
          </div>
        ) : null}

        <FormField id="org-name" label={t("organizations.name")} error={errorOf("name")}>
          {(props) => <input {...props} className={INPUT_CLASS} value={draft.name} maxLength={120} required autoComplete="organization" onChange={(e) => edit({ name: e.target.value })} />}
        </FormField>
        <FormField id="org-slug" label={t("organizations.slug")} hint={t("organizations.slugHint")} error={errorOf("slug")}>
          {(props) => <input {...props} className={`${INPUT_CLASS} tabular`} value={draft.slug} maxLength={63} required spellCheck={false} autoComplete="off" onChange={(e) => edit({ slug: e.target.value.toLowerCase() })} />}
        </FormField>

        <fieldset className="flex flex-col gap-1.5" aria-describedby={errorOf("country_code") ? "org-country-erreur" : undefined}>
          <legend className="text-dense font-medium">{t("organizations.country")}</legend>
          <div className="flex flex-wrap gap-2">
            {COUNTRIES.map((country) => (
              <label key={country} className="flex min-h-10 cursor-pointer items-center gap-2 rounded-md border border-line-2 px-3 has-[:checked]:border-brand has-[:checked]:bg-brand-soft">
                <input type="radio" name="country" value={country} checked={draft.country === country} onChange={() => edit({ country })} className="size-4 accent-[var(--accent)]" />
                {tDynamic("countries", country)}
              </label>
            ))}
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-1.5" aria-describedby={errorOf("capabilities") ? "org-capabilities-erreur" : "org-capabilities-aide"} aria-invalid={errorOf("capabilities") ? true : undefined}>
          <legend className="text-dense font-medium">{t("organizations.capabilities")}</legend>
          <div className="flex flex-wrap gap-2">
            {CAPABILITIES.map((cap) => (
              <label key={cap} className="flex min-h-10 cursor-pointer items-center gap-2 rounded-md border border-line-2 px-3 has-[:checked]:border-brand has-[:checked]:bg-brand-soft">
                <input
                  type="checkbox"
                  checked={draft.capabilities.includes(cap)}
                  onChange={(e) => edit({ capabilities: e.target.checked ? [...draft.capabilities, cap] : draft.capabilities.filter((c) => c !== cap) })}
                  className="size-4 accent-[var(--accent)]"
                />
                {tDynamic("capabilities", cap)}
              </label>
            ))}
          </div>
          {errorOf("capabilities") ? (
            <p id="org-capabilities-erreur" className="flex items-center gap-1.5 text-dense text-crit">
              <AlertTriangleIcon className="size-3.5" aria-hidden />
              {errorOf("capabilities")}
            </p>
          ) : null}
          <p id="org-capabilities-aide" className="text-caption text-fg-2">
            {t("organizations.capabilitiesHint")}
          </p>
        </fieldset>

        <FormField id="org-regulator" label={t("organizations.regulator")} hint={t("organizations.optional")} error={errorOf("regulator")}>
          {(props) => <input {...props} className={INPUT_CLASS} value={draft.regulator} maxLength={40} onChange={(e) => edit({ regulator: e.target.value })} />}
        </FormField>

        <fieldset className="flex flex-col gap-3 rounded-md border border-line p-4">
          <legend className="px-1 text-dense font-medium">{t("organizations.manager")}</legend>
          <FormField id="manager-name" label={t("organizations.managerName")} error={errorOf("first_manager.display_name")}>
            {(props) => <input {...props} className={INPUT_CLASS} value={draft.managerName} maxLength={120} autoComplete="off" onChange={(e) => edit({ managerName: e.target.value })} />}
          </FormField>
          <FormField id="manager-subject" label={t("organizations.managerSubject")} hint={t("organizations.managerSubjectHint")} error={errorOf("first_manager.idp_subject")}>
            {(props) => <input {...props} className={`${INPUT_CLASS} tabular`} value={draft.managerSubject} maxLength={200} spellCheck={false} autoComplete="off" onChange={(e) => edit({ managerSubject: e.target.value })} />}
          </FormField>
          <FormField id="manager-email" label={t("organizations.managerEmail")} hint={t("organizations.managerEmailHint")} error={errorOf("first_manager.email")}>
            {(props) => <input {...props} type="email" className={INPUT_CLASS} value={draft.managerEmail} autoComplete="off" onChange={(e) => edit({ managerEmail: e.target.value })} />}
          </FormField>
        </fieldset>

        <FormField
          id="org-template"
          label={t("organizations.template")}
          hint={selected ? t("organizations.templateContents", { accounts: selected.contents.ledger_accounts, rules: selected.contents.rules, plans: selected.contents.plans, acts: selected.contents.acts }) : t("organizations.templateHint")}
          error={errorOf("template")}
        >
          {(props) => (
            <select {...props} className={INPUT_CLASS} value={draft.template} disabled={templatesLoading} onChange={(e) => edit({ template: e.target.value })}>
              {choices.length === 0 ? <option value="">{templatesLoading ? t("states.loading") : t("organizations.noTemplate")}</option> : null}
              {choices.map((c) => (
                <option key={c.value} value={c.value}>
                  {t("organizations.templateOption", { label: c.template.label, code: c.template.code, version: c.template.version })}
                </option>
              ))}
            </select>
          )}
        </FormField>

        <Button type="submit" className="h-10 self-start px-4 text-dense" disabled={create.isPending} aria-busy={create.isPending || undefined}>
          {create.isPending ? <Loader2Icon className="motion-safe:animate-spin" aria-hidden /> : null}
          {t("organizations.submit")}
        </Button>
      </form>
    </Panel>
  );
}

function OnboardedList({ items }: { items: OrganizationOnboarding[] }) {
  return (
    <Panel aria-labelledby="onboarded-list-title">
      <div className="flex flex-col gap-1 border-b border-line p-4">
        <h2 id="onboarded-list-title" className="text-title font-semibold">
          {t("organizations.listTitle")}
        </h2>
        <p className="text-fg-2">{t("organizations.listIntro")}</p>
      </div>
      {items.length === 0 ? (
        <EmptyState title={t("organizations.listEmptyTitle")} body={t("organizations.listEmptyBody")} />
      ) : (
        <Table aria-label={t("organizations.listTitle")}>
          <TableHeader>
            <TableRow>
              <TableHead>{t("organizations.name")}</TableHead>
              <TableHead>{t("organizations.country")}</TableHead>
              <TableHead>{t("organizations.template")}</TableHead>
              <TableHead>{t("organizations.status")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((o) => (
              <TableRow key={o.organization.id} data-testid="onboarded-row">
                <TableCell>
                  <div className="font-medium">{o.organization.name}</div>
                  <div className="tabular text-caption text-fg-2">{o.organization.slug}</div>
                </TableCell>
                <TableCell>{tDynamic("countries", o.organization.country_code)}</TableCell>
                <TableCell className="tabular">{t("organizations.templateRef", { code: o.template.code, version: o.template.version })}</TableCell>
                <TableCell>
                  <Badge tone="neutral">{t("organizations.statusIntegration")}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Panel>
  );
}

function TemplatesTable({ items }: { items: ConfigurationTemplate[] }) {
  const sorted = [...items].sort((a, b) => a.code.localeCompare(b.code) || b.version - a.version);
  return (
    <Table aria-label={t("organizations.templatesTitle")}>
      <TableHeader>
        <TableRow>
          <TableHead>{t("organizations.templateCol")}</TableHead>
          <TableHead>{t("organizations.country")}</TableHead>
          <TableHead className="text-right">{t("organizations.contentsCol")}</TableHead>
          <TableHead>{t("organizations.publishedCol")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((tpl) => (
          <TableRow key={tpl.id} data-testid="template-row">
            <TableCell>
              <div className="font-medium">{tpl.label}</div>
              <div className="tabular text-caption text-fg-2">{t("organizations.templateRef", { code: tpl.code, version: tpl.version })}</div>
            </TableCell>
            <TableCell>{tDynamic("countries", tpl.country_code)}</TableCell>
            <TableCell className="text-right text-caption">{t("organizations.contentsShort", { rules: tpl.contents.rules, plans: tpl.contents.plans, acts: tpl.contents.acts })}</TableCell>
            <TableCell className="tabular">{formatDate(tpl.created_at)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function PublishTemplate() {
  const [code, setCode] = useState("");
  const [country, setCountry] = useState<CountryCode>("CI");
  const [label, setLabel] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const publish = useCreateConfigurationTemplate();
  const codeError = submitted && !/^[a-z0-9][a-z0-9-]{1,39}$/.test(code) ? t("organizations.errors.code") : null;
  const labelError = submitted && (label.trim().length < 1 || label.length > 120) ? t("organizations.errors.required") : null;
  const problem = publish.error instanceof ApiError ? publish.error.problem : null;
  return (
    <form
      noValidate
      className="flex flex-col gap-3 border-t border-line p-4"
      aria-labelledby="publish-title"
      onSubmit={(e) => {
        e.preventDefault();
        setSubmitted(true);
        if (!/^[a-z0-9][a-z0-9-]{1,39}$/.test(code) || label.trim().length < 1) return;
        publish.mutate({ code, country_code: country, label: label.trim() }, { onSuccess: () => setSubmitted(false) });
      }}
    >
      <h3 id="publish-title" className="text-dense font-semibold">
        {t("organizations.publishTitle")}
      </h3>
      <p className="text-caption text-fg-2">{t("organizations.publishHint")}</p>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_1fr]">
        <FormField id="tpl-code" label={t("organizations.templateCode")} error={codeError ?? problem?.errors?.find((e) => e.field === "code")?.message ?? null}>
          {(props) => <input {...props} className={`${INPUT_CLASS} tabular`} value={code} maxLength={40} spellCheck={false} autoComplete="off" onChange={(e) => setCode(e.target.value.toLowerCase())} />}
        </FormField>
        <FormField id="tpl-country" label={t("organizations.country")}>
          {(props) => (
            <select {...props} className={INPUT_CLASS} value={country} onChange={(e) => setCountry(e.target.value as CountryCode)}>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>
                  {tDynamic("countries", c)}
                </option>
              ))}
            </select>
          )}
        </FormField>
        <FormField id="tpl-label" label={t("organizations.templateLabel")} error={labelError ?? problem?.errors?.find((e) => e.field === "label")?.message ?? null}>
          {(props) => <input {...props} className={INPUT_CLASS} value={label} maxLength={120} onChange={(e) => setLabel(e.target.value)} />}
        </FormField>
      </div>
      {publish.isError && !problem?.errors?.length ? <ErrorState error={publish.error} /> : null}
      {publish.isSuccess ? (
        <p role="status" className="flex items-center gap-1.5 text-ok" data-testid="template-published">
          <CheckIcon className="size-4" aria-hidden />
          {t("organizations.published", { code: publish.data.code, version: publish.data.version })}
        </p>
      ) : null}
      <Button type="submit" variant="outline" className="h-10 self-start px-4 text-dense" disabled={publish.isPending} aria-busy={publish.isPending || undefined}>
        {publish.isPending ? <Loader2Icon className="motion-safe:animate-spin" aria-hidden /> : null}
        {t("organizations.publish")}
      </Button>
    </form>
  );
}
