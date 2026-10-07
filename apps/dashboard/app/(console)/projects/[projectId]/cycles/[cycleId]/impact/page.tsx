import { ImpactScreen } from "@/components/screens/ImpactScreen";

export default async function ImpactPage({
  params,
}: {
  params: Promise<{ projectId: string; cycleId: string }>;
}) {
  const { projectId, cycleId } = await params;
  return <ImpactScreen projectId={projectId} cycleId={cycleId} />;
}
