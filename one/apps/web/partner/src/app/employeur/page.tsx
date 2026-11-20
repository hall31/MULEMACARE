import type { Metadata } from "next";
import { EmployerView } from "@/features/employer/employer-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: t("employer.title") };

export default function EmployerPage() {
  return <EmployerView />;
}
