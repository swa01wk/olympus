"use client";

import { EmptyState } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";

export function UnsupportedStage({
  cycleType,
  stage,
}: {
  cycleType: DeliveryCycleType;
  stage: string;
}) {
  return (
    <StageWorkspaceFrame>
      <EmptyState
        title="Unknown stage"
        description={`${cycleType} · ${stage} is not mapped to a workspace view.`}
      />
    </StageWorkspaceFrame>
  );
}
