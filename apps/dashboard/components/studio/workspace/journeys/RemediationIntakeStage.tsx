"use client";

import { EmptyState, Panel } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { useQuery } from "@tanstack/react-query";
import { fetchCycleKnowledge } from "@/src/api/resources";
import { queryKeys } from "@/src/api/query-keys";

export function RemediationIntakeStage({ cycleId }: { cycleId: string }) {
  const knowledge = useQuery({
    queryKey: queryKeys.knowledge(cycleId),
    queryFn: () => fetchCycleKnowledge(cycleId),
  });

  return (
    <StageWorkspaceFrame>
      <Panel title="Remediation intake" sub="Findings and knowledge driving this cycle">
        {(knowledge.data ?? []).length === 0 && !knowledge.isLoading && (
          <EmptyState title="No intake records" description="Link findings from assurance or inbox." />
        )}
        <ul className="ol-ws-bullets">
          {(knowledge.data ?? []).map((k) => (
            <li key={k.id}>{k.statement}</li>
          ))}
        </ul>
      </Panel>
    </StageWorkspaceFrame>
  );
}
