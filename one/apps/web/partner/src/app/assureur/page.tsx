import type { Metadata } from "next";
import { PortfolioView } from "@/features/insurer/portfolio-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: t("insurer.title") };

export default function InsurerPage() {
  return <PortfolioView />;
}
