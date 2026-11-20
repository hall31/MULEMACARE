import type { Metadata } from "next";
import { t } from "@/i18n";
import { PublicPaymentScreen } from "@/payment/PublicPaymentScreen";

export const metadata: Metadata = { title: t("pay.metaTitle"), robots: { index: false, follow: false } };

/** Lien de paiement diaspora : page publique, sans compte (URL `<MULEMA_PAYMENT_PUBLIC_BASE_URL>/<jeton>`). */
export default async function PublicPaymentPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PublicPaymentScreen token={token} />;
}
