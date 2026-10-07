"use client";

import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { TaskContractCard } from "@/components/tasks/TaskContractCard";
import { TaskDag } from "@/components/tasks/TaskDag";
import { EmptyState, Panel } from "@/components/primitives";
import { isMaterializedTaskId } from "@/lib/task-plan-dag";
import { screenHref } from "@/lib/nav-hrefs";
import { useDeliveryCycle } from "@/src/api/hooks/use-olympus-queries";
import {
  useTaskContract,
  useTaskDagView,
  useTaskEligibility,
} from "@/src/api/hooks/use-drill-queries";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

export function TaskDagScreen({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const searchParams = useSearchParams();
  const initial = searchParams.get("selected") ?? undefined;
  const [selectedId, setSelectedId] = useState<string | undefined>(initial);
  const [mode, setMode] = useState<"graph" | "list">("graph");

  const cycle = useDeliveryCycle(cycleId);
  const dagView = useTaskDagView(cycleId);
  const materializedSelection = selectedId && isMaterializedTaskId(selectedId) ? selectedId : undefined;
  const contract = useTaskContract(materializedSelection);
  const eligibility = useTaskEligibility(materializedSelection);

  const nodes = dagView.nodes;
  const edges = dagView.edges;

  const whyLines = useMemo(() => {
    const reasons = eligibility.data?.reasons ?? [];
    return reasons;
  }, [eligibility.data]);

  const mapHref = screenHref("S02", projectId, cycleId);

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S04">
      <Panel title="S04 · Task DAG" sub="Durable work boundaries and scheduler predicates">
        {dagView.isPreview && (
          <p className="text-sm ol-muted mb-3 border border-dashed border-[var(--border-strong)] rounded-md px-3 py-2">
            Showing <strong>proposed</strong> tasks from task plan{" "}
            {dagView.planStatus ? `(${dagView.planStatus})` : ""} — durable Task rows appear after
            the plan is accepted and the cycle reaches Work.
          </p>
        )}
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
        {dagView.isLoading && <p className="ol-muted text-sm">Loading DAG…</p>}
        {!dagView.isLoading && nodes.length === 0 && (
          <EmptyState
            title="No tasks yet"
            description={`This cycle is in ${cycle.data?.state ?? "—"}. Tasks and dependencies appear here after task plan generation (preview) and acceptance (materialized rows). Resolve clarifications and advance planning on the control-plane map.`}
          >
            <Link href={mapHref} className="text-sm underline ol-muted">
              Back to control-plane map
            </Link>
          </EmptyState>
        )}
        {nodes.length > 0 && (
          <TaskDag
            nodes={nodes}
            edges={edges}
            selectedId={selectedId}
            onSelect={setSelectedId}
            mode={mode}
            preview={dagView.isPreview}
          />
        )}
      </Panel>
      {materializedSelection && (
        <div className="grid gap-4 md:grid-cols-2">
          <Panel title="Why is this task in this state?" sub="Admission / scheduler guards">
            {eligibility.isLoading && <p className="text-sm ol-muted">Evaluating…</p>}
            {!eligibility.isLoading && (
              <ul className="text-sm list-disc ml-4">
                {whyLines.length ? (
                  whyLines.map((l) => <li key={l}>{l}</li>)
                ) : (
                  <li>{eligibility.data?.eligible ? "Eligible to run." : "No detail returned."}</li>
                )}
              </ul>
            )}
          </Panel>
          <TaskContractCard contract={contract.data ?? null} />
        </div>
      )}
      {selectedId && !materializedSelection && dagView.isPreview && (
        <Panel title="Task contract" sub="Available after plan acceptance">
          <p className="text-sm ol-muted">
            Proposed task <code className="ol-id">{selectedId.replace(/^plan:/, "")}</code> — contract
            and eligibility load from materialized Task records only.
          </p>
        </Panel>
      )}
    </CycleDrillFrame>
  );
}
