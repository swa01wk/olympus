import { OutcomeScreen } from "@/components/screens/OutcomeScreen";

export default async function OutcomePage({
  params,
}: {
  params: Promise<{ projectId: string; cycleId: string }>;
}) {
  const { projectId, cycleId } = await params;
  return <OutcomeScreen projectId={projectId} cycleId={cycleId} />;
}
