import type { Metadata } from "next";
import { t } from "@/i18n";
import { TourScreen } from "@/onboarding/TourScreen";

export const metadata: Metadata = { title: `${t("tour.invite.start")} · ${t("app.name")}` };

/** Découverte de l'espace en trois étapes (première visite, rejouable). */
export default function TourPage() {
  return <TourScreen />;
}
