import type { Metadata } from "next";
import { MetricsView } from "@/features/metrics/metrics-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: `${t("metrics.title")} · ${t("app.name")}` };

export default function MetricsPage() {
  return <MetricsView />;
}
