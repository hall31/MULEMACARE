"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { t } from "@/i18n";
import { browserDeviceStores, purgeDeviceData } from "@/lib/device-data";
import { BrandLogo, BrandName } from "@/brand/brand-context";
import { BrandMark, ScreenTitle, Seal } from "@/ui/ui";

/**
 * Déconnexion : efface la mémoire des requêtes, la carte enregistrée (et toute clé de l'espace)
 * et les caches du service worker, puis le dit. Hors de la coquille de l'espace : aucun écran
 * authentifié n'est monté, donc aucune requête ne peut réécrire la carte après l'effacement.
 * La fin de session chez le fournisseur d'identité reste à brancher (QUESTIONS.md Q-P1W-07).
 */
export function SignedOutScreen() {
  const queryClient = useQueryClient();
  const [purged, setPurged] = useState(false);

  useEffect(() => {
    let alive = true;
    void purgeDeviceData({ ...browserDeviceStores(), queryClient }).then(() => {
      if (alive) setPurged(true);
    });
    return () => {
      alive = false;
    };
  }, [queryClient]);

  return (
    <div className="member">
      <header className="m-top">
        <span className="m-brand-link">
          <BrandLogo fallback={<BrandMark />} />
          <b className="m-brand">
            <BrandName />
          </b>
        </span>
      </header>
      <main id="contenu" className="m-main">
        <div className="m-body m-single">
          <div className="outcome outcome-ok" data-testid="signed-out" data-purged={purged || undefined}>
            <Seal kind={purged ? "ok" : "empty"} />
            <ScreenTitle>{t("signedOut.title")}</ScreenTitle>
            <p role="status" aria-live="polite">
              {purged ? t("signedOut.text") : t("signedOut.busy")}
            </p>
            <Link className="btn btn-primary btn-block" data-variant="primary" href="/">
              {t("signedOut.back")}
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
