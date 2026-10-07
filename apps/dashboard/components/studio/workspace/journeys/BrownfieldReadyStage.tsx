"use client";

import { EmptyState, Panel } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";

export function BrownfieldReadyStage() {
  return (
    <StageWorkspaceFrame>
      <Panel title="Ready for change" sub="Brownfield onboarding complete">
        <EmptyState
          title="READY"
          description="Start a Feature Change or Bug Fix cycle from the project console when the project is READY_FOR_CHANGE."
        />
      </Panel>
    </StageWorkspaceFrame>
  );
}
