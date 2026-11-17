import { RunScreen } from "@/components/simple/RunScreen";

export default async function RunPage({ params }: { params: Promise<{ cycleId: string }> }) {
  const { cycleId } = await params;
  return <RunScreen cycleId={cycleId} />;
}
