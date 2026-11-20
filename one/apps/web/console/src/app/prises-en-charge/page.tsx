import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingRows } from "@/components/states";
import { ClaimsView } from "@/features/claims/claims-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: `${t("claims.title")} · ${t("app.name")}` };

export default function ClaimsPage() {
  return (
    <Suspense fallback={<LoadingRows />}>
      <ClaimsView />
    </Suspense>
  );
}
