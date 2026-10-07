"use client";

import { PlanningStage } from "@/components/studio/workspace/PlanningStage";

/** REMEDIATION machine state in brownfield — reuse planning workspace. */
export function BrownfieldRemediationStage({
  projectId,
  cycleId,
}: {
  projectId: string;
  cycleId: string;
}) {
  return <PlanningStage projectId={projectId} cycleId={cycleId} />;
}
