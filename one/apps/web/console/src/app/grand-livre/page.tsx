import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingRows } from "@/components/states";
import { LedgerView } from "@/features/ledger/ledger-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: `${t("ledger.title")} · ${t("app.name")}` };

export default function LedgerPage() {
  return (
    <Suspense fallback={<LoadingRows />}>
      <LedgerView />
    </Suspense>
  );
}
