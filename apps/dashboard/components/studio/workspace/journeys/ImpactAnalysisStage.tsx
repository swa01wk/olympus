"use client";

import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { ImpactWorkspacePanel } from "@/components/studio/workspace/embed/ImpactWorkspacePanel";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import { runImpactAssessment } from "@/src/api/commands";

export function ImpactAnalysisStage({ cycleId }: { cycleId: string }) {
  return (
    <StageWorkspaceFrame>
      <StudioMutationAction
        label="Run impact assessment"
        path={`/delivery-cycles/${cycleId}/impact-assessments`}
        body={{}}
        onRun={(idem) => runImpactAssessment(cycleId, {}, idem)}
      />
      <ImpactWorkspacePanel cycleId={cycleId} />
    </StageWorkspaceFrame>
  );
}
