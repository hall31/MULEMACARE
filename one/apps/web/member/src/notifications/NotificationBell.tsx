"use client";

import Link from "next/link";
import { useState } from "react";
import { t, tp } from "@/i18n";
import { deferred } from "@/ui/deferred";
import { Icon } from "@/ui/ui";

/**
 * Le calcul des notifications (lectures de la carte, des soins, des cotisations et des
 * bénéficiaires, règles de `derive.ts`) est chargé à part, après le premier affichage : il ne pèse
 * pas sur le JavaScript initial de la carte (PERFORMANCE.md). La cloche, elle, est rendue tout de
 * suite à sa taille définitive ; seul le compteur arrive ensuite (pastille absolue, pas de saut).
 */
const UnreadProbe = deferred(() => import("./UnreadProbe").then((m) => m.default));

export function NotificationBell({ current }: { current: boolean }) {
  const [unread, setUnread] = useState(0);
  const label = unread > 0 ? tp("nav.notifications.unread", unread) : t("nav.notifications");
  return (
    <Link href="/notifications" className="m-bell" aria-label={label} aria-current={current ? "page" : undefined} data-testid="notification-bell" data-unread={unread}>
      <Icon name="bell" />
      {unread > 0 ? (
        <span className="m-badge" aria-hidden="true">
          {unread}
        </span>
      ) : null}
      <UnreadProbe onChange={setUnread} />
    </Link>
  );
}
