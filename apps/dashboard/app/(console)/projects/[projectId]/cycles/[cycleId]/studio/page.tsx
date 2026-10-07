import { StudioScreen } from "@/components/screens/StudioScreen";
import { Suspense } from "react";

export default async function StudioPage({
  params,
}: {
  params: Promise<{ projectId: string; cycleId: string }>;
}) {
  const { projectId, cycleId } = await params;
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading studio…</p>}>
      <StudioScreen projectId={projectId} cycleId={cycleId} />
    </Suspense>
  );
}
