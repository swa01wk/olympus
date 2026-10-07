import { AssuranceScreen } from "@/components/screens/AssuranceScreen";

export default async function AssurancePage({
  params,
}: {
  params: Promise<{ projectId: string; cycleId: string }>;
}) {
  const { projectId, cycleId } = await params;
  return <AssuranceScreen projectId={projectId} cycleId={cycleId} />;
}
