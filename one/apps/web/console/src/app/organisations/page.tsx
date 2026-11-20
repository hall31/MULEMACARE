import type { Metadata } from "next";
import { OrganizationsView } from "@/features/platform/organizations-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: `${t("organizations.title")} · ${t("app.name")}` };

export default function OrganizationsPage() {
  return <OrganizationsView />;
}
