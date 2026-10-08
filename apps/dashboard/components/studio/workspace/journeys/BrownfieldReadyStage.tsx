"use client";

import { EmptyState, Panel } from "@/components/primitives";
import { ProductSpecView } from "@/components/studio/ProductSpecView";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";

export function BrownfieldReadyStage({ projectId }: { projectId: string }) {
  return (
    <StageWorkspaceFrame>
      <ProductSpecView projectId={projectId} />
      <Panel title="Ready for change" sub="Brownfield onboarding complete">
        <EmptyState
          title="READY"
          description="Start a Feature Change or Bug Fix cycle from the project console when the project is READY_FOR_CHANGE."
        />
      </Panel>
    </StageWorkspaceFrame>
  );
}
