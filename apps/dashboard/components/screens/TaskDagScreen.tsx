"use client";

import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { TaskContractCard } from "@/components/tasks/TaskContractCard";
import { TaskDag } from "@/components/tasks/TaskDag";
import { Panel } from "@/components/primitives";
import {
  useTaskContract,
  useTaskDag,
  useTaskEligibility,
} from "@/src/api/hooks/use-drill-queries";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

export function TaskDagScreen({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const searchParams = useSearchParams();
  const initial = searchParams.get("selected") ?? undefined;
  const [selectedId, setSelectedId] = useState<string | undefined>(initial);
  const [mode, setMode] = useState<"graph" | "list">("graph");

  const dag = useTaskDag(cycleId);
  const contract = useTaskContract(selectedId);
  const eligibility = useTaskEligibility(selectedId);

  const nodes = dag.data?.nodes ?? [];
  const edges = dag.data?.edges ?? [];

  const whyLines = useMemo(() => {
    const reasons = eligibility.data?.reasons ?? [];
    return reasons;
  }, [eligibility.data]);

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S04">
      <Panel title="S04 · Task DAG" sub="Durable work boundaries and scheduler predicates">
        <div className="ol-gtool mb-4">
          <div className="ol-seg">
            <button
              type="button"
              className={`ol-seg-i ${mode === "graph" ? "is-on" : ""}`}
              onClick={() => setMode("graph")}
            >
              Graph
            </button>
            <button
              type="button"
              className={`ol-seg-i ${mode === "list" ? "is-on" : ""}`}
              onClick={() => setMode("list")}
            >
              List
            </button>
          </div>
        </div>
        {dag.isLoading && <p className="ol-muted text-sm">Loading DAG…</p>}
        <TaskDag
          nodes={nodes}
          edges={edges}
          selectedId={selectedId}
          onSelect={setSelectedId}
          mode={mode}
        />
      </Panel>
      {selectedId && (
        <div className="grid gap-4 md:grid-cols-2">
          <Panel title="Why is this task in this state?" sub="Admission / scheduler guards">
            {eligibility.isLoading && <p className="text-sm ol-muted">Evaluating…</p>}
            {!eligibility.isLoading && (
              <ul className="text-sm list-disc ml-4">
                {whyLines.length ? whyLines.map((l) => <li key={l}>{l}</li>) : (
                  <li>{eligibility.data?.eligible ? "Eligible to run." : "No detail returned."}</li>
                )}
              </ul>
            )}
          </Panel>
          <TaskContractCard contract={contract.data ?? null} />
        </div>
      )}
    </CycleDrillFrame>
  );
}
