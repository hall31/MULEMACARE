"use client";

import { BookOpenIcon, Building2Icon, ClipboardCheckIcon, GaugeIcon, HomeIcon, LayersIcon, MonitorIcon, MoonIcon, PaletteIcon, SunIcon, UsersIcon, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState, type ReactNode } from "react";
import { useAccess, useCurrentUser, useWorkQueue } from "@/api/queries";
import { useBrand } from "@/brand/brand-context";
import type { Role } from "@/api/types";
import { t, tDynamic, type MessageKey } from "@/i18n";
import { cn } from "@/lib/cn";
import { DEMO_ROLES, isDemoRole, useSession } from "@/lib/session";
import { CommandPalette } from "@/features/palette/command-palette";
import { MeasureConsentBanner, MeasureSwitch } from "./measure-consent";
import { NativeSelect, ToggleGroup, ToggleGroupItem } from "./ui/misc";

interface NavItem {
  href: string;
  label: MessageKey;
  icon: LucideIcon;
  roles: Role[];
  group: "groupPilotage" | "groupOperations" | "groupFinance" | "groupAdmin";
}

/** Pages et rôles autorisés : reflète `x-roles` des opérations appelées par chaque page. */
export const NAV: NavItem[] = [
  { href: "/", label: "nav.home", icon: HomeIcon, roles: ["gestionnaire", "medecin_conseil", "admin"], group: "groupPilotage" },
  { href: "/mesure", label: "nav.metrics", icon: GaugeIcon, roles: ["gestionnaire", "admin"], group: "groupPilotage" },
  { href: "/prises-en-charge", label: "nav.claims", icon: ClipboardCheckIcon, roles: ["gestionnaire", "medecin_conseil", "admin"], group: "groupOperations" },
  { href: "/adherents", label: "nav.members", icon: UsersIcon, roles: ["gestionnaire", "admin"], group: "groupOperations" },
  { href: "/grand-livre", label: "nav.ledger", icon: BookOpenIcon, roles: ["gestionnaire", "admin"], group: "groupFinance" },
  { href: "/produits", label: "nav.products", icon: LayersIcon, roles: ["gestionnaire", "admin"], group: "groupFinance" },
  // P3 : marque blanche (admin de l'organisation) et accueil d'organisation (admin de plateforme).
  { href: "/marque", label: "nav.branding", icon: PaletteIcon, roles: ["admin"], group: "groupAdmin" },
  { href: "/organisations", label: "nav.organizations", icon: Building2Icon, roles: ["admin_plateforme"], group: "groupAdmin" },
];

const THEME_KEY = "mulemacare-one.console.theme";
type ThemeMode = "light" | "dark" | "auto";

function ThemeControl() {
  const [mode, setMode] = useState<ThemeMode>("auto");
  useEffect(() => {
    const stored = window.localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") setMode(stored);
  }, []);
  useEffect(() => {
    const root = document.documentElement;
    if (mode === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", mode);
    window.localStorage.setItem(THEME_KEY, mode);
  }, [mode]);
  const items: { value: ThemeMode; icon: LucideIcon; label: MessageKey }[] = [
    { value: "light", icon: SunIcon, label: "theme.light" },
    { value: "dark", icon: MoonIcon, label: "theme.dark" },
    { value: "auto", icon: MonitorIcon, label: "theme.auto" },
  ];
  return (
    <ToggleGroup
      type="single"
      value={mode}
      onValueChange={(v) => (v ? setMode(v as ThemeMode) : undefined)}
      aria-label={t("theme.label")}
      className="w-full"
    >
      {items.map(({ value, icon: Icon, label }) => (
        <ToggleGroupItem key={value} value={value} aria-label={t(label)} className="flex-1 justify-center px-1.5">
          <Icon aria-hidden />
          <span>{t(label)}</span>
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}

function SessionControl() {
  const session = useSession();
  const me = useCurrentUser();
  const role = me.data?.roles[0]?.role;
  return (
    <div className="flex flex-col gap-2 text-xs">
      <span className="text-fg-2">{t("session.connectedAs")}</span>
      <p className="flex flex-col">
        <span className="font-medium text-fg">{me.data?.user.display_name ?? t("common.none")}</span>
        <span data-testid="current-role" className="text-fg-2">
          {role ? tDynamic("roles", role) : t("common.none")}
        </span>
      </p>
      {session.mode === "demo" ? (
        <>
          <label htmlFor="demo-profile" className="text-fg-2">
            {t("session.demoProfile")}
          </label>
          <NativeSelect
            id="demo-profile"
            value={session.role ?? ""}
            onChange={(e) => (isDemoRole(e.target.value) ? session.setRole(e.target.value) : undefined)}
            aria-describedby="demo-profile-hint"
          >
            {DEMO_ROLES.map((r) => (
              <option key={r} value={r}>
                {tDynamic("roles", r)}
              </option>
            ))}
          </NativeSelect>
          <p id="demo-profile-hint" className="text-fg-2">
            {t("session.demoProfileHint")}
          </p>
        </>
      ) : null}
    </div>
  );
}

/**
 * Marque de l'organisation (P3) : son logo (déjà assaini, rendu en image seulement) ou son initiale
 * sur l'accent ; sans marque, le monogramme MulemaCare. Le nom est dit à côté : le logo est décoratif.
 */
function BrandMark() {
  const brand = useBrand();
  if (brand?.logoSrc) {
    // <img> simple : data-URI ou URL déjà assainie, aucun optimiseur d'images ni requête tierce.
    return <img src={brand.logoSrc} alt="" width={28} height={28} className="size-7 shrink-0 rounded-md object-contain" data-testid="brand-logo" />;
  }
  return (
    <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-md bg-brand font-display text-sm font-bold text-brand-fg">
      {brand ? brand.displayName.charAt(0).toLocaleUpperCase("fr") : t("app.monogram")}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const brand = useBrand();
  const pathname = usePathname();
  const session = useSession();
  const { roles, has } = useAccess();
  const me = useCurrentUser();
  const queue = useWorkQueue(has("gestionnaire") || has("medecin_conseil") || has("admin"));
  const org = me.data?.organization;
  const visible = NAV.filter((item) => item.roles.some((r) => roles.includes(r)));
  const current = NAV.find((item) => (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)));

  let lastGroup: NavItem["group"] | null = null;

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)]">
      <a
        href="#contenu"
        className="sr-only z-50 rounded-btn bg-surface px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        {t("app.skipToContent")}
      </a>
      <aside className="flex flex-col gap-4 border-b border-line bg-surface px-3 py-4 lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto lg:border-r lg:border-b-0">
        <div className="flex items-center gap-2.5 px-2">
          <BrandMark />
          <span className="flex flex-col leading-tight">
            <span className="font-display text-[15px] font-semibold" data-testid="brand-name">
              {brand?.displayName ?? t("app.name")}
            </span>
            <span className="text-[11px] text-fg-2">
              {org ? t("app.tagline", { country: tDynamic("countries", org.country_code) }) : t("common.none")}
            </span>
          </span>
        </div>

        <nav aria-label={t("nav.label")} className="flex flex-row gap-0.5 overflow-x-auto lg:flex-col">
          {visible.map((item) => {
            const header = item.group !== lastGroup ? item.group : null;
            lastGroup = item.group;
            const active = current?.href === item.href;
            const Icon = item.icon;
            return (
              <div key={item.href} className="contents">
                {header ? (
                  <span className="hidden px-2.5 pt-2.5 pb-1 text-[11px] font-semibold tracking-[0.08em] text-fg-2 uppercase lg:block">
                    {t(`nav.${header}`)}
                  </span>
                ) : null}
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 rounded-sm px-2.5 py-[7px] font-medium whitespace-nowrap text-fg-2 hover:bg-sunk hover:text-fg",
                    active && "bg-brand-soft text-brand hover:bg-brand-soft hover:text-brand",
                  )}
                >
                  <Icon className="size-4 shrink-0" aria-hidden />
                  {t(item.label)}
                  {item.href === "/prises-en-charge" && queue.data ? (
                    <span className="tabular ml-auto text-[11px]" aria-label={t("nav.inReviewCount", { count: queue.data.claims_in_review })}>
                      {queue.data.claims_in_review}
                    </span>
                  ) : null}
                </Link>
              </div>
            );
          })}
        </nav>

        <div className="mt-auto flex flex-col gap-4">
          <SessionControl />
          {session.token !== null ? <MeasureSwitch /> : null}
          <ThemeControl />
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-line bg-surface px-6 py-3">
          <p className="text-[13px] text-fg-2">
            {me.data?.roles[0] ? tDynamic("roles", me.data.roles[0].role) : null}
            {current ? (
              <>
                {" / "}
                <span className="font-semibold text-fg">{t(current.label)}</span>
              </>
            ) : null}
          </p>
          <span className="flex-1" />
          {session.token !== null ? (
            <Suspense fallback={null}>
              <CommandPalette />
            </Suspense>
          ) : null}
          {org ? (
            <span className="hidden items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-xs text-fg-2 md:inline-flex">
              <span aria-hidden className="size-1.5 rounded-full bg-ok" />
              {t("app.residency", {
                country: org.country_code,
                city: tDynamic("residencyCity", org.country_code),
              })}
            </span>
          ) : null}
          {session.mode === "demo" ? (
            <span className="hidden rounded-full border border-line px-2.5 py-0.5 text-xs text-fg-2 md:inline-flex">
              {t("app.demoData")}
            </span>
          ) : null}
        </header>
        <main id="contenu" tabIndex={-1} className="flex w-full max-w-[1320px] flex-col gap-5 px-4 pt-6 pb-16 outline-none md:px-6">
          {session.mode === "unconfigured" ? (
            <div role="alert" className="rounded-lg border border-line bg-surface p-5">
              <p className="font-semibold">{t("session.notConfiguredTitle")}</p>
              <p className="text-fg-2">{t("session.notConfiguredBody")}</p>
            </div>
          ) : (
            <>
              {session.token !== null ? <MeasureConsentBanner /> : null}
              {children}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
