"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { browserStore } from "@/card/last-card";
import { t } from "@/i18n";
import { Button, Icon } from "@/ui/ui";
import { readTour, shouldInvite, writeTour } from "./tour";

/**
 * Invitation de première visite sur « Ma carte » : non bloquante (la carte et « Présenter ma carte »
 * restent au-dessus, l'adhérent peut être au comptoir), passable (« Plus tard »), et la découverte
 * reste rejouable : une fois passée ou terminée, l'invitation devient le lien « Revoir la découverte
 * de l'espace ».
 */
export function TourInvite() {
  // Inconnu au rendu serveur : rien n'est affiché avant la lecture du téléphone (pas de saut).
  const [show, setShow] = useState<boolean | null>(null);
  useEffect(() => {
    const store = browserStore();
    setShow(store !== null && shouldInvite(readTour(store)));
  }, []);
  if (show === null) return null;
  if (!show) return <TourReplayLink />;
  return (
    <section className="panel tour-invite" aria-labelledby="tour-invite-t" data-testid="tour-invite">
      <div className="pad stack">
        <h2 className="panel-t" id="tour-invite-t">
          {t("tour.invite.title")}
        </h2>
        <p>{t("tour.invite.text")}</p>
        <div className="actions">
          <Link className="btn btn-secondary" href="/decouverte" data-testid="tour-start">
            <Icon name="info" />
            <span>{t("tour.invite.start")}</span>
          </Link>
          <Button
            variant="secondary"
            onClick={() => {
              const store = browserStore();
              if (store) writeTour(store, "passe", new Date());
              setShow(false);
            }}
          >
            {t("tour.invite.later")}
          </Button>
        </div>
      </div>
    </section>
  );
}

/** Lien permanent pour rejouer la découverte. */
export function TourReplayLink() {
  return (
    <Link className="link-row" href="/decouverte" data-testid="tour-replay">
      <Icon name="info" />
      <span>{t("tour.replay")}</span>
    </Link>
  );
}
