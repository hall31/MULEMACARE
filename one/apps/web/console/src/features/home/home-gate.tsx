"use client";

import { ArrowRightIcon } from "lucide-react";
import Link from "next/link";
import { useAccess } from "@/api/queries";
import { LoadingRows, PageHeader, Panel } from "@/components/states";
import { t } from "@/i18n";
import { HomeView } from "./home-view";

/**
 * L'administrateur de plateforme n'a aucun accès métier (Q-P3-01) : son accueil mène à l'accueil
 * d'organisations au lieu d'appeler la file de travail (qui lui répondrait 403).
 */
export function HomeGate() {
  const { has, ready } = useAccess();
  if (!ready) return <LoadingRows rows={3} />;
  if (has("admin_plateforme") && !has("gestionnaire") && !has("medecin_conseil") && !has("admin")) {
    return (
      <>
        <PageHeader eyebrow={t("organizations.eyebrow")} title={t("home.platformTitle")} />
        <Panel className="flex flex-col items-start gap-3 p-5">
          <p className="max-w-[70ch] text-fg-2">{t("home.platformBody")}</p>
          <Link href="/organisations" className="inline-flex min-h-10 items-center gap-1.5 font-medium text-brand underline underline-offset-4">
            {t("home.platformLink")}
            <ArrowRightIcon className="size-4" aria-hidden />
          </Link>
        </Panel>
      </>
    );
  }
  return <HomeView />;
}
