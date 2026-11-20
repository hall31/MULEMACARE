import { TrackingScreen } from "@/claims/TrackingScreen";

export default async function TrackingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TrackingScreen claimId={id} />;
}
