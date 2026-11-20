import type { Metadata } from "next";
import { t } from "@/i18n";
import { NotificationsScreen } from "@/notifications/NotificationsScreen";

export const metadata: Metadata = { title: `${t("notif.title")} · ${t("app.name")}` };

/** Centre de notifications dérivé des données du contrat (aucun envoi). */
export default function NotificationsPage() {
  return <NotificationsScreen />;
}
