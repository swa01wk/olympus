import { IntegrationsScreen } from "@/components/screens/IntegrationsScreen";
import { Suspense } from "react";

export default async function IntegrationsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading…</p>}>
      <IntegrationsScreen projectId={projectId} />
    </Suspense>
  );
}
