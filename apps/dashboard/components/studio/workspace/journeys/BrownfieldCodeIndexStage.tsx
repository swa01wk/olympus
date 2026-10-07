"use client";

import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { CodeIntelligenceWorkspacePanel } from "@/components/studio/workspace/embed/CodeIntelligenceWorkspacePanel";

export function BrownfieldCodeIndexStage({
  projectId,
  cycleId,
}: {
  projectId: string;
  cycleId: string;
}) {
  return (
    <StageWorkspaceFrame>
      <CodeIntelligenceWorkspacePanel projectId={projectId} cycleId={cycleId} />
    </StageWorkspaceFrame>
  );
}
