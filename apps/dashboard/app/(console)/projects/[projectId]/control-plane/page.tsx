"use client";

import { cycleMapPath } from "@/lib/cycle-url";
import { useProjectOverview } from "@/src/api/hooks/use-olympus-queries";
import { useRouter } from "next/navigation";
import { use, useEffect } from "react";

export default function ControlPlaneLegacyRedirect({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  const router = useRouter();
  const overview = useProjectOverview(projectId);

  useEffect(() => {
    const cycleId = overview.data?.active_cycle_id as string | undefined;
    if (cycleId) {
      router.replace(cycleMapPath(projectId, cycleId));
    } else if (!overview.isLoading) {
      router.replace(`/projects/${projectId}`);
    }
  }, [overview.data, overview.isLoading, projectId, router]);

  return <p className="ol-main ol-muted">Redirecting to cycle map…</p>;
}
