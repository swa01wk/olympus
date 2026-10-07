"use client";

import { EmptyState, Panel } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { useRecoveryProposals } from "@/src/api/hooks/use-journey-queries";
import { useQuery } from "@tanstack/react-query";
import { fetchCycleKnowledge } from "@/src/api/resources";
import { queryKeys } from "@/src/api/query-keys";

export function BrownfieldRecoveredSpecStage({ cycleId }: { cycleId: string }) {
  const recovery = useRecoveryProposals(cycleId);
  const knowledge = useQuery({
    queryKey: queryKeys.knowledge(cycleId),
    queryFn: () => fetchCycleKnowledge(cycleId),
  });

  return (
    <StageWorkspaceFrame>
      <Panel title="Recovery proposals" sub={`GET /delivery-cycles/${cycleId}/recovery`}>
        {(recovery.data?.proposals ?? []).length === 0 && !recovery.isLoading && (
          <EmptyState title="No proposals" description="Recovery agent output appears here." />
        )}
        <ul className="ol-ws-bullets">
          {(recovery.data?.proposals ?? []).map((p, i) => (
            <li key={i}>
              <pre className="ol-ws-pre ol-body-sm">{JSON.stringify(p, null, 2)}</pre>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Recovered knowledge" sub="Cycle knowledge items">
        {(knowledge.data ?? []).length === 0 && !knowledge.isLoading && (
          <p className="ol-body-sm ol-muted">No knowledge items yet.</p>
        )}
        <ul className="ol-ws-bullets">
          {(knowledge.data ?? []).map((k) => (
            <li key={k.id}>
              <span className="ol-id">{k.class}</span> {k.statement}
            </li>
          ))}
        </ul>
      </Panel>
    </StageWorkspaceFrame>
  );
}
