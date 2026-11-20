import type { Metadata } from "next";
import { t } from "@/i18n";
import { SignedOutScreen } from "@/member/SignedOutScreen";

export const metadata: Metadata = { title: t("signedOut.metaTitle"), robots: { index: false, follow: false } };

/** Fin de session sur ce téléphone : données locales et caches effacés. */
export default function SignedOutPage() {
  return <SignedOutScreen />;
}
