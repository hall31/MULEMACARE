import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingRows } from "@/components/states";
import { MembersView } from "@/features/members/members-view";
import { t } from "@/i18n";

export const metadata: Metadata = { title: `${t("members.title")} · ${t("app.name")}` };

export default function MembersPage() {
  return (
    <Suspense fallback={<LoadingRows />}>
      <MembersView />
    </Suspense>
  );
}
