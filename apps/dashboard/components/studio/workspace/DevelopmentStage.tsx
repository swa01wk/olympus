"use client";

import { ExecutionTimeline } from "@/components/executions/ExecutionTimeline";
import { EmptyState, Panel } from "@/components/primitives";
import { TaskDag } from "@/components/tasks/TaskDag";
import { TaskContractCard } from "@/components/tasks/TaskContractCard";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { isMaterializedTaskId } from "@/lib/task-plan-dag";
import { useTaskDagView, useTaskContract, useTaskEligibility } from "@/src/api/hooks/use-drill-queries";
import { useExecutionsForTasks, useTasks } from "@/src/api/hooks/use-olympus-queries";
import type { Execution } from "@/src/api/types/core";
import Link from "next/link";
import { useMemo, useState } from "react";

/** Task DAG + executions (embedded from S04 / S05). */
export function DevelopmentStage({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  void projectId;
  const [selectedId, setSelectedId] = useState<string | undefined>();
  const [mode, setMode] = useState<"graph" | "list">("graph");

  const dagView = useTaskDagView(cycleId);
  const tasks = useTasks(cycleId);
  const taskIds = useMemo(() => (tasks.data ?? []).map((t) => t.id), [tasks.data]);
  const execQueries = useExecutionsForTasks(taskIds);
  const materializedSelection =
    selectedId && isMaterializedTaskId(selectedId) ? selectedId : undefined;
  const contract = useTaskContract(materializedSelection);
  const eligibility = useTaskEligibility(materializedSelection);

  const executions = useMemo(() => {
    const all: Execution[] = [];
    for (const q of execQueries) {
      if (q.data) all.push(...q.data);
    }
    return all.sort((a, b) => b.attempt_number - a.attempt_number);
  }, [execQueries]);

  return (
    <StageWorkspaceFrame>
      <Panel title="Task DAG" sub="Development work boundaries">
        {dagView.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
        {!dagView.isLoading && dagView.nodes.length === 0 && (
          <EmptyState title="No tasks" description="Accept a task plan in Planning first." />
        )}
        {dagView.nodes.length > 0 && (
          <>
            <div className="ol-gtool mb-3">
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
            <TaskDag
              nodes={dagView.nodes}
              edges={dagView.edges}
              selectedId={selectedId}
              onSelect={setSelectedId}
              mode={mode}
              preview={dagView.isPreview}
            />
          </>
        )}
      </Panel>
      {materializedSelection && (
        <div className="ol-ws-split">
          <Panel title="Task eligibility" sub="Scheduler guards">
            <ul className="ol-ws-bullets">
              {(eligibility.data?.reasons ?? []).map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </Panel>
          <TaskContractCard contract={contract.data ?? null} />
        </div>
      )}
      <Panel title="Executions" sub="Attempts for cycle tasks">
        {executions.length === 0 && !tasks.isLoading && (
          <EmptyState title="No executions" description="Tasks have not been attempted yet." />
        )}
        <ExecutionTimeline
          executions={executions}
          selectedId={undefined}
          onSelect={() => {}}
        />
        {executions.slice(0, 8).map((ex) => (
          <p key={ex.id} className="ol-body-sm">
            <Link className="ol-idlink" href={`/executions/${ex.id}`}>
              {ex.key}
            </Link>{" "}
            — attempt {ex.attempt_number}
          </p>
        ))}
      </Panel>
    </StageWorkspaceFrame>
  );
}
