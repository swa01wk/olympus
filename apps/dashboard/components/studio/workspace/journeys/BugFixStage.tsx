"use client";

import { EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import {
  useDefectDetail,
  useDefectReproductions,
  useDefectRootCause,
  useDefects,
} from "@/src/api/hooks/use-journey-queries";
import { useMemo, useState } from "react";

export function BugFixStage({
  projectId,
  cycleId,
  stage,
}: {
  projectId: string;
  cycleId: string;
  stage: "TRIAGE" | "REPRODUCTION" | "EXPECTED_BEHAVIOR" | "ROOT_CAUSE" | "REGRESSION";
}) {
  const defects = useDefects(projectId);
  const forCycle = useMemo(
    () => (defects.data ?? []).filter((d) => d.delivery_cycle_id === cycleId),
    [defects.data, cycleId],
  );
  const [defectId, setDefectId] = useState<string | undefined>();
  const activeId = defectId ?? forCycle[0]?.id;
  const detail = useDefectDetail(activeId);
  const repros = useDefectReproductions(stage === "REPRODUCTION" ? activeId : undefined);
  const rca = useDefectRootCause(stage === "ROOT_CAUSE" ? activeId : undefined);

  const titles: Record<typeof stage, string> = {
    TRIAGE: "Triage",
    REPRODUCTION: "Reproduction",
    EXPECTED_BEHAVIOR: "Expected behavior",
    ROOT_CAUSE: "Root cause",
    REGRESSION: "Regression",
  };

  return (
    <StageWorkspaceFrame>
      <Panel title={titles[stage]} sub={`Defect records · ${stage}`}>
        {forCycle.length === 0 && !defects.isLoading && (
          <EmptyState title="No defect for cycle" description="Intake a defect for this bug-fix cycle." />
        )}
        <ul className="ol-ws-list">
          {forCycle.map((d) => (
            <li key={d.id}>
              <button
                type="button"
                className={`ol-ws-list-btn ${activeId === d.id ? "is-on" : ""}`}
                onClick={() => setDefectId(d.id)}
              >
                {d.key} — {d.title} <StatusBadge status={d.status} />
              </button>
            </li>
          ))}
        </ul>
        {detail.data && (
          <div className="ol-ws-spec-read">
            <p>{detail.data.description}</p>
            {stage === "TRIAGE" && detail.data.triage != null && (
              <pre className="ol-ws-pre">{JSON.stringify(detail.data.triage, null, 2)}</pre>
            )}
            {stage === "EXPECTED_BEHAVIOR" && (
              <p className="ol-body-sm ol-muted">
                Linked AC ids: {detail.data.expected_ac_ids.join(", ") || "—"}
              </p>
            )}
          </div>
        )}
        {stage === "REPRODUCTION" && (
          <ul className="ol-ws-bullets">
            {(repros.data ?? []).map((r, i) => (
              <li key={i}>{JSON.stringify(r)}</li>
            ))}
          </ul>
        )}
        {stage === "ROOT_CAUSE" && rca.data && (
          <pre className="ol-ws-pre">{JSON.stringify(rca.data, null, 2)}</pre>
        )}
        {stage === "REGRESSION" && (
          <p className="ol-body-sm ol-muted">
            Regression checks run in Integration / Assurance — use those stages for evidence.
          </p>
        )}
      </Panel>
    </StageWorkspaceFrame>
  );
}
