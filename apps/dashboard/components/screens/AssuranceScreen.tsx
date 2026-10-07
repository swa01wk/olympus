"use client";

import { EvidenceMatrix } from "@/components/assurance/EvidenceMatrix";
import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { Panel, Sha } from "@/components/primitives";
import { useIcAssurance } from "@/src/api/hooks/use-drill-queries";
import { useIntegrationCandidates } from "@/src/api/hooks/use-olympus-queries";

export function AssuranceScreen({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const ics = useIntegrationCandidates(cycleId);
  const ic = ics.data?.[ics.data.length - 1];
  const assurance = useIcAssurance(ic?.id);

  const data = assurance.data ?? {};
  const obligations = (data.obligations as Record<string, unknown>[]) ?? [];
  const evidence = (data.evidence as Record<string, unknown>[]) ?? [];
  const coverage = (data.coverage as Record<string, unknown>[]) ?? [];
  const targetSha = ic?.integrated_sha ?? ic?.base_sha;

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S09">
      <Panel title="S09 · Assurance" sub="Independent evidence and gate state">
        {ic && (
          <p className="text-sm mb-3">
            Exact target: {targetSha ? <Sha value={targetSha} /> : "—"} · IC {ic.key}
          </p>
        )}
        {!ic && <p className="text-sm ol-muted">No integration candidate — readiness-style view when applicable.</p>}
        {assurance.isLoading && <p className="text-sm ol-muted">Loading assurance view…</p>}
        <EvidenceMatrix
          obligations={obligations}
          evidence={evidence}
          coverage={coverage}
          targetSha={targetSha}
        />
      </Panel>
    </CycleDrillFrame>
  );
}
