"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAccess, useCurrentUser } from "@/api/queries";
import { useBrand } from "@/brand/brand-context";
import { t, tDynamic, type MessageKey } from "@/i18n";
import { cn } from "@/lib/cn";
import { DEMO_ROLES, isDemoRole, useSession } from "@/lib/session";
import { Loading } from "./states";
import { Icon, type IconName } from "./ui";

interface NavItem {
  href: string;
  label: MessageKey;
  icon: IconName;
  roles: string[];
}

/** Espaces et rôles autorisés : reflète `x-roles` des opérations appelées par chaque espace. */
export const NAV: NavItem[] = [
  { href: "/assureur", label: "nav.insurer", icon: "chart", roles: ["assureur", "admin"] },
  { href: "/employeur", label: "nav.employer", icon: "users", roles: ["employeur"] },
];

const THEME_KEY = "mulemacare-one.partenaires.theme";
type ThemeMode = "light" | "dark" | "auto";
const THEMES: { value: ThemeMode; icon: IconName; label: MessageKey }[] = [
  { value: "light", icon: "sun", label: "theme.light" },
  { value: "dark", icon: "moon", label: "theme.dark" },
  { value: "auto", icon: "monitor", label: "theme.auto" },
];

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
  return (
    <div role="group" aria-label={t("theme.label")} className="grid grid-cols-3 gap-1 rounded-lg border border-line bg-sunk p-1">
      {THEMES.map((item) => (
        <button
          key={item.value}
          type="button"
          aria-pressed={mode === item.value}
          onClick={() => setMode(item.value)}
          className={cn("inline-flex min-h-12 min-w-0 flex-col items-center justify-center gap-0.5 rounded-md px-1 text-caption font-medium", mode === item.value ? "bg-surface text-fg shadow-[var(--shadow-1)]" : "text-fg-2 hover:text-fg")}
        >
          <Icon name={item.icon} />
          {t(item.label)}
        </button>
      ))}
    </div>
  );
}

/** Marque de l'organisation (P3) : logo assaini en image, ou initiale ; nom écrit à côté. */
function BrandBlock() {
  const brand = useBrand();
  const me = useCurrentUser();
  return (
    <div className="flex items-center gap-2.5">
      {brand?.logoSrc ? (
        <img src={brand.logoSrc} alt="" width={32} height={32} className="size-8 shrink-0 rounded-md object-contain" data-testid="brand-logo" />
      ) : (
        <span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-md bg-brand-deep font-display font-bold text-brand-on-deep">
          {brand ? brand.displayName.charAt(0).toLocaleUpperCase("fr") : t("app.monogram")}
        </span>
      )}
      <span className="flex min-w-0 flex-col">
        <span className="truncate font-display font-semibold" data-testid="brand-name">
          {brand?.displayName ?? t("app.name")}
        </span>
        <span className="truncate text-caption text-fg-2">{me.data ? me.data.organization.name : t("app.tagline")}</span>
      </span>
    </div>
  );
}

function SessionControl() {
  const session = useSession();
  const me = useCurrentUser();
  return (
    <div className="flex flex-col gap-2">
      <p className="flex flex-col">
        <span className="text-caption text-fg-2">{t("session.connectedAs")}</span>
        <span className="font-medium">{me.data?.user.display_name ?? t("common.none")}</span>
        <span className="text-fg-2" data-testid="current-role">
          {me.data?.roles[0] ? tDynamic("roles", me.data.roles[0].role) : t("common.none")}
        </span>
      </p>
      {session.mode === "demo" ? (
        <>
          <label htmlFor="demo-profile" className="text-caption text-fg-2">
            {t("session.demoProfile")}
          </label>
          <select
            id="demo-profile"
            value={session.role ?? ""}
            onChange={(e) => (isDemoRole(e.target.value) ? session.setRole(e.target.value) : undefined)}
            className="min-h-12 w-full rounded-md border border-line-2 bg-surface px-3 text-dense"
            aria-describedby="demo-profile-aide"
          >
            {DEMO_ROLES.map((r) => (
              <option key={r} value={r}>
                {tDynamic("roles", r)}
              </option>
            ))}
          </select>
          <p id="demo-profile-aide" className="text-caption text-fg-2">
            {t("session.demoHint")}
          </p>
        </>
      ) : null}
    </div>
  );
}

/**
 * Coquille des espaces partenaires : barre latérale à partir de 1024 px, barre du haut en dessous ;
 * navigation limitée aux espaces du rôle ; apparence clair / sombre / auto. Densité console (14 px),
 * zones tactiles de 48 px (les partenaires consultent aussi sur téléphone).
 */
export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/";
  const session = useSession();
  const { roles } = useAccess();
  const visible = NAV.filter((item) => item.roles.some((r) => roles.some((x) => x === r)));
  const router = useRouter();
  const ready = roles.length > 0;
  // Profil changé : un espace qui n'est plus permis mène à celui du nouveau rôle.
  useEffect(() => {
    const current = NAV.find((item) => pathname.startsWith(item.href));
    if (ready && current && !visible.includes(current) && visible[0]) router.replace(visible[0].href);
  }, [ready, pathname, visible, router]);
  return (
    <div className="grid min-h-dvh grid-cols-1 lg:grid-cols-[248px_minmax(0,1fr)]">
      <a href="#contenu" className="sr-only z-50 rounded-btn bg-surface px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2">
        {t("app.skip")}
      </a>
      <aside className="flex flex-col gap-4 border-b border-line bg-surface p-4 lg:sticky lg:top-0 lg:h-dvh lg:overflow-y-auto lg:border-r lg:border-b-0">
        <BrandBlock />
        <nav aria-label={t("nav.label")} className="flex flex-row flex-wrap gap-1 lg:flex-col">
          {visible.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn("flex min-h-12 items-center gap-2.5 rounded-md px-3 font-medium", active ? "bg-accent-2 text-fg" : "text-fg-2 hover:bg-sunk hover:text-fg")}
              >
                <Icon name={item.icon} className={active ? "text-accent" : undefined} />
                {t(item.label)}
              </Link>
            );
          })}
        </nav>
        <div className="flex flex-col gap-4 lg:mt-auto">
          <SessionControl />
          <ThemeControl />
        </div>
      </aside>
      <main id="contenu" tabIndex={-1} className="flex w-full max-w-[1120px] min-w-0 flex-col gap-6 px-4 pt-6 pb-16 outline-none md:px-6">
        {session.mode === "unconfigured" ? (
          <div role="alert" className="rounded-lg border border-line bg-surface p-5">
            <p className="font-semibold">{t("session.notConfiguredTitle")}</p>
            <p className="text-fg-2">{t("session.notConfiguredBody")}</p>
          </div>
        ) : (
          children
        )}
      </main>
    </div>
  );
}

/** Garde d'interface : l'API refuse de toute façon (403), on l'explique avant d'appeler. */
export function RequireRole({ roles, children }: { roles: string[]; children: ReactNode }) {
  const access = useAccess();
  if (!access.ready) return <Loading rows={4} />;
  if (!roles.some((r) => access.has(r))) {
    return (
      <div role="alert" className="flex items-start gap-2 rounded-lg border border-line bg-surface p-5">
        <Icon name="lock" className="mt-0.5 text-fg-2" />
        <div>
          <p className="font-semibold">{t("states.forbiddenTitle")}</p>
          <p className="text-fg-2">{t("states.forbiddenBody")}</p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
