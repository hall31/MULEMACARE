import type { Metadata } from "next";
import { ProductsView } from "@/features/products/products-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: `${t("products.title")} · ${t("app.name")}` };

export default function ProductsPage() {
  return <ProductsView />;
}
