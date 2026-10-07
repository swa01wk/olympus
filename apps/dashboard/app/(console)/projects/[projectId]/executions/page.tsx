import { ExecutionsScreen } from "@/components/screens/ExecutionsScreen";
import { Suspense } from "react";

export default async function ExecutionsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading…</p>}>
      <ExecutionsScreen projectId={projectId} />
    </Suspense>
  );
}
