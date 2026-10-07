import { TaskDagScreen } from "@/components/screens/TaskDagScreen";
import { Suspense } from "react";

export default async function TasksPage({
  params,
}: {
  params: Promise<{ projectId: string; cycleId: string }>;
}) {
  const { projectId, cycleId } = await params;
  return (
    <Suspense fallback={<p className="ol-main ol-muted">Loading tasks…</p>}>
      <TaskDagScreen projectId={projectId} cycleId={cycleId} />
    </Suspense>
  );
}
