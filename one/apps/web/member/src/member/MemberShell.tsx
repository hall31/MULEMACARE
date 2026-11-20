"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { BrandLogo, useBrand } from "@/brand/brand-context";
import { t, type MessageKey } from "@/i18n";
import { preloadTelemetry, track } from "@/lib/track";
import { NotificationBell } from "@/notifications/NotificationBell";
import { deferred } from "@/ui/deferred";
import { BrandMark, Button, Icon, type IconName } from "@/ui/ui";
import { useOnline } from "./queries";

/**
 * Bandeau de consentement à la mesure : il n'existe pas au rendu serveur (le choix est sur le
 * téléphone) et n'apparaît qu'après lecture du choix ; son code est donc chargé à part, hors du
 * JavaScript initial (PERFORMANCE.md), sans changer le moment où il s'affiche.
 */
const MeasureConsent = deferred(() => import("./MeasureConsent").then((m) => m.default));

interface Tab {
  href: string;
  icon: IconName;
  short: MessageKey;
  long: MessageKey;
  match: (path: string) => boolean;
}

const TABS: Tab[] = [
  { href: "/", icon: "card", short: "nav.card", long: "nav.card.long", match: (p) => p === "/" || p.startsWith("/carte") },
  { href: "/soins", icon: "clip", short: "nav.claims", long: "nav.claims.long", match: (p) => p.startsWith("/soins") },
  { href: "/cotisations", icon: "wallet", short: "nav.contributions", long: "nav.contributions.long", match: (p) => p.startsWith("/cotisations") },
  { href: "/famille", icon: "users", short: "nav.family", long: "nav.family.long", match: (p) => p.startsWith("/famille") },
];

/**
 * Coquille de l'espace adhérent (planche, écran 03) : barre du haut avec la marque, navigation
 * dans la barre à partir de 768 px, barre d'onglets collée en bas sous 768 px, cloche des
 * notifications dérivées. Bandeau hors ligne persistant (warn) tant que le réseau manque : ce qui
 * reste possible et ce qui ne l'est pas. « Se déconnecter » mène à `/deconnexion`,
 * qui efface ce que l'espace garde sur le téléphone une fois les écrans de l'espace fermés (aucune
 * requête en cours ne peut alors réécrire la carte).
 */
export function MemberShell({ children }: { children: ReactNode }) {
  const path = usePathname() ?? "/";
  const online = useOnline();
  const router = useRouter();
  const brand = useBrand();
  // Mesure produit : bandeau hors ligne vu (envoyé au retour du réseau, rien hors ligne).
  useEffect(() => {
    if (!online) track("offline_banner_seen");
  }, [online]);
  useEffect(preloadTelemetry, []);
  return (
    <div className="member">
      <a className="skip" href="#contenu">
        {t("nav.skip")}
      </a>
      <header className="m-top">
        <Link href="/" className="m-brand-link" aria-label={t("nav.home")}>
          <BrandLogo fallback={<BrandMark />} />
          <b className="m-brand" data-testid="brand-name">
            {brand?.displayName ?? t("app.name")}
          </b>
        </Link>
        <nav className="m-nav" aria-label={t("nav.label")}>
          {TABS.map((tab) => (
            <Link key={tab.href} href={tab.href} aria-current={tab.match(path) ? "page" : undefined}>
              {t(tab.long)}
            </Link>
          ))}
        </nav>
        <NotificationBell current={path.startsWith("/notifications")} />
        <Button variant="secondary" icon="signOut" className="m-signout" data-testid="sign-out" onClick={() => router.replace("/deconnexion")}>
          {t("nav.signOut")}
        </Button>
      </header>
      {online ? null : (
        <div className="alert tone-warn banner" role="status" data-testid="offline-banner">
          <Icon name="wifiOff" />
          <div className="alert-body">
            <b>{t("net.offline")}</b>
            <span className="detail">{t("net.offline.detail")}</span>
            <ul className="offline-caps">
              <li data-testid="offline-can">
                <Icon name="check" />
                <span>{t("net.offline.can")}</span>
              </li>
              <li data-testid="offline-cannot">
                <Icon name="x" />
                <span>{t("net.offline.cannot")}</span>
              </li>
            </ul>
          </div>
        </div>
      )}
      <main id="contenu" className="m-main">
        <MeasureConsent />
        {children}
      </main>
      {/* Découverte : parcours guidé sans barre d'onglets (on en sort par « Passer » ou par la marque). */}
      {path.startsWith("/decouverte") ? null : (
        <nav className="m-tabbar" aria-label={t("nav.mobileLabel")} data-testid="tabbar">
          {TABS.map((tab) => (
            <Link key={tab.href} href={tab.href} aria-current={tab.match(path) ? "page" : undefined}>
              <span className="ib">
                <Icon name={tab.icon} />
              </span>
              {t(tab.short)}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
