import type { Metadata } from "next";
import { BrandingView } from "@/features/branding/branding-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: `${t("branding.title")} · ${t("app.name")}` };

export default function BrandingPage() {
  return <BrandingView />;
}
