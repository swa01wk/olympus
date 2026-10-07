import { CycleMapScreen } from "@/components/screens/CycleMapScreen";
import { Suspense } from "react";

export default async function CycleMapPage({
  params,
}: {
  params: Promise<{ projectId: string; cycleId: string }>;
}) {
  const { projectId, cycleId } = await params;
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading cycle map…</p>}>
      <CycleMapScreen projectId={projectId} cycleId={cycleId} />
    </Suspense>
  );
}
