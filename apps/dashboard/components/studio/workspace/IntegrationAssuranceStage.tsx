"use client";

import { EvidenceMatrix } from "@/components/assurance/EvidenceMatrix";
import { Panel, Sha } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { useIcAssurance } from "@/src/api/hooks/use-drill-queries";
import { useIntegrationCandidates } from "@/src/api/hooks/use-olympus-queries";

/** Embedded assurance view (S09) for INTEGRATION and ASSURANCE stages. */
export function IntegrationAssuranceStage({
  projectId,
  cycleId,
  stage,
}: {
  projectId: string;
  cycleId: string;
  stage: string;
}) {
  void projectId;
  const ics = useIntegrationCandidates(cycleId);
  const ic = ics.data?.[ics.data.length - 1];
  const assurance = useIcAssurance(ic?.id);

  const data = assurance.data ?? {};
  const obligations = (data.obligations as Record<string, unknown>[]) ?? [];
  const evidence = (data.evidence as Record<string, unknown>[]) ?? [];
  const coverage = (data.coverage as Record<string, unknown>[]) ?? [];
  const targetSha = ic?.integrated_sha ?? ic?.base_sha;

  return (
    <StageWorkspaceFrame>
      <Panel
        title={stage === "INTEGRATION" ? "Integration" : "Assurance"}
        sub="Integration candidate and evidence matrix"
      >
        {ic && (
          <p className="ol-body-sm mb-3">
            Target: {targetSha ? <Sha value={targetSha} /> : "—"} · IC {ic.key}
          </p>
        )}
        {!ic && (
          <p className="ol-body-sm ol-muted">No integration candidate yet for this cycle.</p>
        )}
        {assurance.isLoading && <p className="ol-body-sm ol-muted">Loading assurance view…</p>}
        <EvidenceMatrix
          obligations={obligations}
          evidence={evidence}
          coverage={coverage}
          targetSha={targetSha}
        />
      </Panel>
    </StageWorkspaceFrame>
  );
}
