import { TraceabilityScreen } from "@/components/screens/TraceabilityScreen";
import { Suspense } from "react";

export default async function LineagePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading…</p>}>
      <TraceabilityScreen projectId={projectId} />
    </Suspense>
  );
}
