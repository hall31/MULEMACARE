"use client";

import { ArrowLeftIcon, BuildingIcon, FileCheckIcon, FileTextIcon, SearchIcon, UserIcon, WifiOffIcon, type LucideIcon } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Dialog as DialogPrimitive } from "radix-ui";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { useAccess, useAskJoe, useClaim, useDraftDecision, useSearch } from "@/api/queries";
import type { DecisionDraft, JoeAnswer, JoeQuestionRequest, SearchHit, Source } from "@/api/types";
import { UnsourcedAnswerError } from "@/api/joe-guard";
import { ErrorState, OPEN_PALETTE_EVENT } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/misc";
import { t, tDynamic } from "@/i18n";
import { cn } from "@/lib/cn";
import { useOnline } from "@/lib/online";
import { useTrack } from "@/lib/use-telemetry";
import { buildGroups, flatten, isPaletteShortcut, moveActive, type PaletteGroup, type PaletteOption } from "./palette-model";

const HIT_ICON: Record<SearchHit["type"], LucideIcon> = { member: UserIcon, claim: FileTextIcon, provider: BuildingIcon };

/** Monogramme de JOE : « J » sur émeraude profond (jamais d'étincelle ni de pictogramme « IA »). */
export function JoeMark({ className }: { className?: string }) {
  return (
    <span aria-hidden className={cn("grid size-6 shrink-0 place-items-center rounded-md bg-brand-deep font-display text-caption font-bold text-brand-on-deep", className)}>
      {t("joe.monogram")}
    </span>
  );
}

/** Retarde la recherche pendant la frappe (une requête par pause, pas par touche). */
function useDebounced(value: string, delayMs = 200): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/** Vrai seulement si `active` dure plus de 300 ms : pas de squelette qui clignote (contrat §8). */
function useDelayed(active: boolean, delayMs = 300): boolean {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!active) {
      setShown(false);
      return;
    }
    const timer = window.setTimeout(() => setShown(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [active, delayMs]);
  return active && shown;
}

type View = { mode: "search" } | { mode: "answer"; question: string } | { mode: "draft"; claimId: string; number: string };

/**
 * Palette ⌘K / Ctrl+K de la console (Phase 2, voie A) : recherche d'adhérents, de dossiers et de
 * prestataires (operationId `search`) et questions à JOE (`askJoe`), avec ses sources et le rappel
 * « JOE recommande, la décision reste humaine ». Pour le médecin-conseil, sur un dossier en revue
 * ouvert : brouillon de décision (`draftClaimDecision`), affiché comme brouillon, avec un bouton qui
 * ouvre le dossier et n'approuve jamais.
 *
 * Accessibilité : fenêtre modale (Radix Dialog : focus piégé, Échap, retour du focus au
 * déclencheur), champ `combobox` relié à une `listbox` groupée (`aria-activedescendant`), flèches,
 * Début, Fin, Entrée. Aucune donnée médicale : ni la recherche ni JOE n'en renvoient.
 */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const viaKeyboard = useRef(false);
  const trackEvent = useTrack();

  // Mesure produit : ouverture au clavier ou au bouton (rien d'autre).
  useEffect(() => {
    if (open) trackEvent("palette_opened", { variant: viaKeyboard.current ? "clavier" : "bouton" });
    viaKeyboard.current = false;
  }, [open, trackEvent]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!isPaletteShortcut(event)) return;
      event.preventDefault();
      viaKeyboard.current = true;
      setOpen((current) => !current);
    };
    const onRequest = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_PALETTE_EVENT, onRequest);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener(OPEN_PALETTE_EVENT, onRequest);
    };
  }, []);

  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <button
          ref={triggerRef}
          type="button"
          aria-keyshortcuts="Control+K Meta+K"
          data-testid="palette-trigger"
          className="inline-flex h-8 min-w-0 items-center gap-2 rounded-md border border-line-2 bg-surface px-2.5 text-dense text-fg-2 hover:bg-sunk hover:text-fg"
        >
          <SearchIcon className="size-4 shrink-0" aria-hidden />
          <span className="truncate">{t("palette.trigger")}</span>
          <kbd aria-hidden className="ml-2 hidden rounded-sm border border-line px-1.5 font-sans text-caption text-fg-2 sm:inline">
            {t("palette.shortcut")}
          </kbd>
        </button>
      </DialogPrimitive.Trigger>
      {open ? <PaletteDialog onClose={() => setOpen(false)} /> : null}
    </DialogPrimitive.Root>
  );
}

function PaletteDialog({ onClose }: { onClose: () => void }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const { has } = useAccess();
  const online = useOnline();
  const baseId = useId();
  const listId = `${baseId}-list`;
  const hintId = `${baseId}-hint`;

  const [q, setQ] = useState("");
  const [active, setActive] = useState(-1);
  const [view, setView] = useState<View>({ mode: "search" });
  const debounced = useDebounced(q.trim());
  const search = useSearch(debounced, online && view.mode === "search");
  const ask = useAskJoe();
  const draft = useDraftDecision();
  const trackEvent = useTrack();

  // Contexte de la page : dossier ou adhérent ouvert (transmis à JOE, jamais deviné).
  const openClaimId = pathname.startsWith("/prises-en-charge") ? params.get("dossier") : null;
  const openMemberId = pathname.startsWith("/adherents") ? params.get("adherent") : null;
  const openClaim = useClaim(openClaimId);
  const draftFor =
    has("medecin_conseil") && openClaim.data?.claim.status === "en_revue" ? { claimId: openClaim.data.claim.id, number: openClaim.data.claim.claim_number } : null;

  const hits = useMemo(() => (debounced.length >= 2 ? (search.data?.items ?? []) : []), [debounced, search.data]);
  const groups = useMemo(() => buildGroups({ q, hits, draftFor }), [q, hits, draftFor]);
  const options = useMemo(() => flatten(groups), [groups]);
  const optionId = (index: number) => `${baseId}-opt-${index}`;

  useEffect(() => setActive(options.length > 0 ? 0 : -1), [options.length, q]);

  const go = useCallback(
    (href: string) => {
      onClose();
      router.push(href);
    },
    [onClose, router],
  );

  const askJoe = (question: string, variant: "exemple" | "saisie" = "saisie") => {
    // Mesure produit : la question elle-même n'est jamais envoyée, seulement sa provenance.
    trackEvent("joe_question_asked", { variant });
    const body: JoeQuestionRequest = { question, ...(openClaimId ? { claim_id: openClaimId } : {}), ...(openMemberId ? { member_id: openMemberId } : {}) };
    setView({ mode: "answer", question });
    ask.mutate(body);
  };

  const activate = (option: PaletteOption | undefined) => {
    if (!option) return;
    if (!online && option.kind !== "hit") return;
    switch (option.kind) {
      case "ask":
        askJoe(option.question);
        return;
      case "example": {
        const question = t(`palette.examples.${option.example}`);
        setQ(question);
        askJoe(question, "exemple");
        return;
      }
      case "draft":
        setView({ mode: "draft", claimId: option.claimId, number: option.number });
        draft.mutate(option.claimId);
        return;
      case "hit":
        if (option.hit.type === "member") go(`/adherents?adherent=${encodeURIComponent(option.hit.id)}`);
        else if (option.hit.type === "claim") go(`/prises-en-charge?dossier=${encodeURIComponent(option.hit.id)}`);
        else askJoe(t("palette.askAboutProvider", { name: option.hit.label }));
    }
  };

  const onKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp" || ((event.key === "Home" || event.key === "End") && view.mode === "search")) {
      if (view.mode !== "search") return;
      event.preventDefault();
      setActive((current) => moveActive(current, event.key as "ArrowDown" | "ArrowUp" | "Home" | "End", options.length));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (view.mode === "search") activate(options[active]);
      else if (q.trim().length >= 2) askJoe(q.trim());
    }
  };

  const showList = view.mode === "search";
  const loading = useDelayed(online && showList && debounced.length >= 2 && search.isFetching && !search.data);

  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="scrim fixed inset-0 z-40" />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        data-testid="palette"
        aria-describedby={hintId}
        className="fixed top-[12vh] left-1/2 z-50 flex max-h-[76vh] w-[calc(100vw-32px)] max-w-[640px] -translate-x-1/2 flex-col overflow-hidden rounded-lg border border-line bg-surface shadow-overlay outline-none"
      >
        <DialogPrimitive.Title className="sr-only">{t("palette.title")}</DialogPrimitive.Title>
        <p id={hintId} className="sr-only">
          {t("palette.description")}
        </p>
        <div className="flex items-center gap-2 border-b border-line px-3">
          <SearchIcon className="size-4 shrink-0 text-fg-2" aria-hidden />
          <label htmlFor={`${baseId}-input`} className="sr-only">
            {t("palette.inputLabel")}
          </label>
          <input
            id={`${baseId}-input`}
            role="combobox"
            aria-expanded={showList && options.length > 0}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={showList && active >= 0 ? optionId(active) : undefined}
            autoComplete="off"
            spellCheck={false}
            value={q}
            placeholder={t("palette.placeholder")}
            onChange={(event) => {
              setQ(event.target.value);
              if (view.mode !== "search") setView({ mode: "search" });
            }}
            onKeyDown={onKeyDown}
            className="h-12 min-w-0 flex-1 bg-transparent text-dense text-fg outline-none placeholder:text-fg-2"
          />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {!online ? (
            <div role="status" data-testid="palette-offline" className="m-3 flex items-start gap-2 rounded-md bg-warn-bg px-3 py-2.5 text-dense text-fg">
              <WifiOffIcon className="mt-0.5 size-4 shrink-0 text-warn" aria-hidden />
              <div className="flex flex-col gap-0.5">
                <span className="font-semibold">{t("palette.offlineTitle")}</span>
                <span>{t("palette.offlineBody")}</span>
                <span className="tabular text-caption">{t("palette.offlineCode")}</span>
              </div>
            </div>
          ) : null}

          {showList ? (
            <>
              <p className="px-4 pt-3 text-caption text-fg-2" aria-live="polite" data-testid="palette-status">
                {q.trim().length < 2
                  ? t("palette.hint")
                  : loading
                    ? t("palette.searching")
                    : search.isSuccess && debounced === q.trim()
                      ? t("palette.resultsCount", { count: hits.length })
                      : null}
              </p>
              {loading ? (
                <div className="flex flex-col gap-2 p-3" aria-hidden>
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-4/5" />
                </div>
              ) : null}
              {search.isError ? (
                <div className="p-3">
                  <ErrorState error={search.error} title={t("palette.searchErrorTitle")} onRetry={() => void search.refetch()} />
                </div>
              ) : null}
              <div role="listbox" id={listId} aria-label={t("palette.listLabel")} className="flex flex-col gap-1 p-2">
                {groups.map((group) => (
                  <OptionGroup key={group.key} group={group} baseId={baseId} options={options} active={active} online={online} onHover={setActive} onPick={activate} />
                ))}
              </div>
              {search.isSuccess && debounced === q.trim() && debounced.length >= 2 && hits.length === 0 ? (
                <div className="px-4 pb-4 text-dense" data-testid="palette-empty">
                  <p className="font-semibold">{t("palette.noResults", { q: debounced })}</p>
                  <p className="text-fg-2">{t("palette.noResultsNext")}</p>
                </div>
              ) : null}
            </>
          ) : null}

          {view.mode === "answer" ? (
            <AnswerPanel
              question={view.question}
              pending={ask.isPending}
              error={ask.isError ? ask.error : null}
              answer={ask.data}
              onRetry={() => askJoe(view.question)}
              onBack={() => setView({ mode: "search" })}
              onOpenSource={(source) => {
                if (source.type === "claim") go(`/prises-en-charge?dossier=${encodeURIComponent(source.id)}`);
                else if (source.type === "member") go(`/adherents?adherent=${encodeURIComponent(source.id)}`);
              }}
              canOpenMember={has("gestionnaire") || has("admin")}
            />
          ) : null}

          {view.mode === "draft" ? (
            <DraftPanel
              number={view.number}
              pending={draft.isPending}
              error={draft.isError ? draft.error : null}
              draft={draft.data}
              onRetry={() => draft.mutate(view.claimId)}
              onBack={() => setView({ mode: "search" })}
              onOpen={() => go(`/prises-en-charge?dossier=${encodeURIComponent(view.claimId)}`)}
            />
          ) : null}
        </div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

function optionLabel(option: PaletteOption): string {
  switch (option.kind) {
    case "ask":
      return t("palette.ask", { q: option.question });
    case "example":
      return t(`palette.examples.${option.example}`);
    case "draft":
      return t("palette.draft", { number: option.number });
    case "hit":
      return option.hit.type === "provider" ? t("palette.askAboutProvider", { name: option.hit.label }) : option.hit.label;
  }
}

function OptionGroup({
  group,
  baseId,
  options,
  active,
  online,
  onHover,
  onPick,
}: {
  group: PaletteGroup;
  baseId: string;
  options: PaletteOption[];
  active: number;
  online: boolean;
  onHover: (index: number) => void;
  onPick: (option: PaletteOption) => void;
}) {
  const labelId = `${baseId}-group-${group.key}`;
  return (
    <div role="group" aria-labelledby={labelId}>
      <div id={labelId} role="presentation" className="px-2 pt-2 pb-1 text-caption font-semibold tracking-[0.08em] text-fg-2 uppercase">
        {tDynamic("palette.groups", group.key)}
      </div>
      {group.options.map((option) => {
        const index = options.indexOf(option);
        const disabled = !online && option.kind !== "hit";
        const Icon = option.kind === "hit" ? HIT_ICON[option.hit.type] : option.kind === "draft" ? FileCheckIcon : null;
        return (
          <div
            key={option.id}
            id={`${baseId}-opt-${index}`}
            role="option"
            aria-selected={index === active}
            aria-disabled={disabled || undefined}
            data-testid={`palette-option-${option.kind}`}
            onMouseMove={() => onHover(index)}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onPick(option)}
            className={cn(
              "flex min-h-9 cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-1.5 text-dense",
              index === active && "bg-brand-soft text-fg",
              disabled && "cursor-not-allowed text-fg-2",
            )}
          >
            {Icon ? <Icon className="size-4 shrink-0 text-fg-2" aria-hidden /> : <JoeMark className="size-5 text-caption" />}
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate">{optionLabel(option)}</span>
              {option.kind === "hit" && option.hit.meta ? <span className="truncate text-caption text-fg-2">{option.hit.meta}</span> : null}
            </span>
            {option.kind === "hit" ? <span className="shrink-0 text-caption text-fg-2">{tDynamic("palette.type", option.hit.type)}</span> : null}
          </div>
        );
      })}
    </div>
  );
}

function JoeHeader({ onBack }: { onBack: () => void }) {
  return (
    <div className="flex items-center gap-2.5">
      <JoeMark />
      <span className="flex flex-col leading-tight">
        <span className="font-display font-semibold">{t("joe.name")}</span>
        <span className="text-caption text-fg-2">{t("joe.role")}</span>
      </span>
      <span className="flex-1" />
      <Button variant="ghost" size="sm" onClick={onBack}>
        <ArrowLeftIcon aria-hidden />
        {t("palette.back")}
      </Button>
    </div>
  );
}

function HumanDecisionNotice() {
  return (
    <p role="note" data-testid="joe-human-decision" className="rounded-md border border-line bg-sunk px-3 py-2 text-dense font-medium">
      {t("joe.humanDecision")}
    </p>
  );
}

/** Code stable d'une erreur détectée par l'écran (réponse sans source : E-JOE-01). */
function clientCode(error: unknown): string | undefined {
  return error instanceof UnsourcedAnswerError ? t("joe.unsourced.code") : undefined;
}

function Sources({ sources, onOpen, canOpenMember }: { sources: Source[]; onOpen: (source: Source) => void; canOpenMember: boolean }) {
  // Jamais vide ici : une réponse ou un brouillon sans source est une erreur (api/joe-guard.ts).
  if (sources.length === 0) return null;
  return (
    <section aria-labelledby="joe-sources-t" className="flex flex-col gap-1.5">
      <h3 id="joe-sources-t" className="eyebrow">
        {t("joe.sourcesTitle", { count: sources.length })}
      </h3>
      <ul data-testid="joe-sources" className="flex flex-col gap-1">
        {sources.map((source) => {
          const label = source.label ?? source.id;
          const openable = source.type === "claim" || (source.type === "member" && canOpenMember);
          return (
            <li key={`${source.type}-${source.id}`} className="flex items-center gap-2 text-dense">
              <span className="min-w-28 text-caption text-fg-2">{tDynamic("joe.sourceType", source.type)}</span>
              {openable ? (
                <button type="button" onClick={() => onOpen(source)} className="tabular inline-flex min-h-8 items-center rounded-sm px-1 text-brand underline-offset-2 hover:underline">
                  {label}
                </button>
              ) : (
                <span className="tabular">{label}</span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Thinking() {
  const shown = useDelayed(true);
  return (
    <div role="status" className="flex flex-col gap-2">
      <span className="text-dense text-fg-2">{t("joe.thinking")}</span>
      {shown ? (
        <>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/5" />
        </>
      ) : null}
    </div>
  );
}

function AnswerPanel({
  question,
  pending,
  error,
  answer,
  onRetry,
  onBack,
  onOpenSource,
  canOpenMember,
}: {
  question: string;
  pending: boolean;
  error: unknown;
  answer: JoeAnswer | undefined;
  onRetry: () => void;
  onBack: () => void;
  onOpenSource: (source: Source) => void;
  canOpenMember: boolean;
}) {
  return (
    <section aria-labelledby="joe-answer-t" data-testid="joe-answer" data-kind={answer?.kind} className="flex flex-col gap-3 p-4">
      <JoeHeader onBack={onBack} />
      <p className="text-dense text-fg-2">{question}</p>
      {pending ? <Thinking /> : null}
      {error ? <ErrorState error={error} title={t("joe.errorTitle")} code={clientCode(error)} onRetry={onRetry} /> : null}
      {answer && !pending ? (
        <div aria-live="polite" className="flex flex-col gap-3">
          <h2 id="joe-answer-t" className="text-body font-semibold">
            {answer.kind === "reponse" ? t("joe.answerTitle") : t("joe.refusalTitle")}
          </h2>
          <p data-testid="joe-answer-text">{answer.answer}</p>
          {answer.sources.length > 0 ? (
            <Sources sources={answer.sources} onOpen={onOpenSource} canOpenMember={canOpenMember} />
          ) : (
            // Refus sans source (admis par le contrat) : JOE ne répond pas sans enregistrement.
            <p className="text-dense text-fg-2">{t("joe.noSources")}</p>
          )}
        </div>
      ) : null}
      <HumanDecisionNotice />
    </section>
  );
}

function DraftPanel({
  number,
  pending,
  error,
  draft,
  onRetry,
  onBack,
  onOpen,
}: {
  number: string;
  pending: boolean;
  error: unknown;
  draft: DecisionDraft | undefined;
  onRetry: () => void;
  onBack: () => void;
  onOpen: () => void;
}) {
  return (
    <section aria-labelledby="joe-draft-t" data-testid="joe-draft" className="flex flex-col gap-3 p-4">
      <JoeHeader onBack={onBack} />
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="joe-draft-t" className="text-body font-semibold">
          {t("joe.draft.title", { number })}
        </h2>
        <span data-testid="joe-draft-badge" className="rounded-full border border-dashed border-line-2 bg-sunk px-2.5 py-0.5 text-caption font-medium text-fg">
          {t("joe.draft.badge")}
        </span>
      </div>
      {pending ? <Thinking /> : null}
      {error ? <ErrorState error={error} title={t("joe.draft.errorTitle")} code={clientCode(error)} onRetry={onRetry} /> : null}
      {draft && !pending ? (
        <div aria-live="polite" className="flex flex-col gap-3 rounded-md border border-dashed border-line-2 p-3">
          <p className="font-semibold" data-testid="joe-draft-recommendation">
            {t("joe.draft.recommendation", { value: tDynamic("joe.draft.value", draft.recommendation) })}
          </p>
          <div className="flex flex-col gap-1">
            <h3 className="eyebrow">{t("joe.draft.rationale")}</h3>
            <p data-testid="joe-draft-rationale">{draft.rationale}</p>
          </div>
          <Sources sources={draft.sources} onOpen={() => onOpen()} canOpenMember={false} />
          <p className="text-dense">{t("joe.draft.notApplied")}</p>
        </div>
      ) : null}
      <HumanDecisionNotice />
      <div>
        <Button onClick={onOpen} data-testid="joe-draft-open">
          <FileTextIcon aria-hidden />
          {t("joe.draft.open")}
        </Button>
      </div>
    </section>
  );
}
