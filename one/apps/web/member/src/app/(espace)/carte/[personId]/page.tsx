import { CardScreen } from "@/card/CardScreen";

/** Carte d'un bénéficiaire de MON contrat (getMyCard?person_id=…) : hors contrat, l'API répond 404. */
export default async function BeneficiaryCardPage({ params }: { params: Promise<{ personId: string }> }) {
  const { personId } = await params;
  return <CardScreen personId={personId} />;
}
