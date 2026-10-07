"use client";

import { EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { ExceptionState } from "@/components/truth/ExceptionState";
import { RunningNotice } from "@/components/studio/workspace/RunningNotice";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import { useProjectArchitecture } from "@/src/api/hooks/use-studio-queries";
import { proposeArchitecture, requestArchitectureApproval } from "@/src/api/commands";
import { useState } from "react";

export function ArchitectureStage({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const architecture = useProjectArchitecture(projectId);
  const [runningExecutionId, setRunningExecutionId] = useState<string | null>(null);

  const arch = architecture.data;

  return (
    <StageWorkspaceFrame>
      {architecture.isError && (
        <ExceptionState status="ERROR" reason="Could not load architecture." />
      )}
      {!architecture.isLoading && !arch && (
        <EmptyState
          title="No architecture yet"
          description="Propose architecture to schedule agent work."
        />
      )}
      {arch && (
        <Panel title="Architecture" sub={`v${arch.version} · ${arch.status}`}>
          <StatusBadge status={arch.status} />
          <pre className="ol-ws-pre">{JSON.stringify(arch.body, null, 2)}</pre>
          {arch.contracts.length > 0 && (
            <>
              <h4 className="ol-label">Contracts</h4>
              <ul className="ol-ws-bullets">
                {arch.contracts.map((c) => (
                  <li key={c.key}>
                    {c.key} ({c.kind}) — {c.name}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      )}
      <Panel title="Actions" sub="REST-only generation (not proposable from chat)">
        <StudioMutationAction
          label="Propose architecture"
          path={`/delivery-cycles/${cycleId}/architecture/propose`}
          onRun={async (idem) => {
            const res = await proposeArchitecture(cycleId, idem);
            if (res.execution_id) setRunningExecutionId(res.execution_id);
          }}
        />
        {runningExecutionId && <RunningNotice executionId={runningExecutionId} />}
        {arch && (
          <StudioMutationAction
            label="Request architecture approval"
            path={`/architectures/${arch.id}/approval-request`}
            body={{ delivery_cycle_id: cycleId }}
            onRun={(idem) => requestArchitectureApproval(arch.id, cycleId, idem)}
          />
        )}
      </Panel>
    </StageWorkspaceFrame>
  );
}
