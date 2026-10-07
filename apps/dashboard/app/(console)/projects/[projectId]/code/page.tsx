import { CodeIntelligenceScreen } from "@/components/screens/CodeIntelligenceScreen";
import { Suspense } from "react";

export default async function CodePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading…</p>}>
      <CodeIntelligenceScreen projectId={projectId} />
    </Suspense>
  );
}
