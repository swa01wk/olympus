"use client";

import { EmptyState, Panel, StatusBadge } from "@/components/primitives";
import { TaskDag } from "@/components/tasks/TaskDag";
import { ExceptionState } from "@/components/truth/ExceptionState";
import { ImplementationSpecVersionEditor } from "@/components/studio/editors/ImplementationSpecVersionEditor";
import { StageWorkspaceFrame } from "@/components/studio/workspace/StageWorkspaceFrame";
import { StudioMutationAction } from "@/components/studio/workspace/StudioMutationAction";
import { fetchImplementationSpec } from "@/src/api/resources";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTaskDagView } from "@/src/api/hooks/use-drill-queries";
import {
  useGenerateImplementationSpecs,
  useGenerateTaskPlan,
  useRequestImplementationSpecApproval,
} from "@/src/api/hooks/use-studio-mutations";
import {
  useFeatures,
  useImplementationSpecs,
  useTaskPlans,
} from "@/src/api/hooks/use-studio-queries";
import {
  generateImplementationSpecs,
  generateTaskPlan,
  requestImplementationSpecApproval,
} from "@/src/api/commands";
import { useRegisterStudioFocus } from "@/lib/studio-focus";
import { useState } from "react";

type PlanningTab = "impl" | "plan" | "dag";

export function PlanningStage({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const scope = { projectId, cycleId };
  const [tab, setTab] = useState<PlanningTab>("impl");
  const [dagMode, setDagMode] = useState<"graph" | "list">("graph");
  const features = useFeatures(projectId);
  const genImpl = useGenerateImplementationSpecs(scope);
  const genPlan = useGenerateTaskPlan(scope);
  const plans = useTaskPlans(cycleId);
  const dagView = useTaskDagView(cycleId);
  const latestPlan = plans.data?.[0];
  const [focusSpecId, setFocusSpecId] = useState<string | undefined>();

  useRegisterStudioFocus(
    focusSpecId
      ? { subject_type: "implementation_spec", subject_id: focusSpecId }
      : tab === "plan" && latestPlan
        ? { subject_type: "task_plan", subject_id: latestPlan.id }
        : null,
  );

  const featureRows = features.data ?? [];

  return (
    <StageWorkspaceFrame>
      <div className="ol-seg ol-ws-tabs">
        {(
          [
            ["impl", "Implementation specs"],
            ["plan", "Task plan"],
            ["dag", "DAG"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`ol-seg-i ${tab === id ? "is-on" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <Panel title="Generate" sub="Schedule agent work for this cycle">
        <StudioMutationAction
          label="Generate implementation specs"
          path={`/delivery-cycles/${cycleId}/implementation-specs/generate`}
          disabled={genImpl.isPending}
          onRun={(idem) => generateImplementationSpecs(cycleId, idem)}
        />
        <StudioMutationAction
          label="Generate task plan"
          path={`/delivery-cycles/${cycleId}/task-plan/generate`}
          disabled={genPlan.isPending}
          onRun={(idem) => generateTaskPlan(cycleId, idem)}
        />
      </Panel>
      {tab === "impl" && (
        <Panel title="Implementation specs" sub="Per feature — request approval per spec">
          {features.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
          {featureRows.length === 0 && (
            <EmptyState title="No features" description="Complete product modeling first." />
          )}
          {featureRows.map((f) => (
            <FeatureImplSpecs
              key={f.id}
              featureId={f.id}
              featureKey={f.key}
              cycleId={cycleId}
              scope={scope}
              focusSpecId={focusSpecId}
              onFocusSpec={setFocusSpecId}
            />
          ))}
        </Panel>
      )}
      {tab === "plan" && (
        <Panel title="Task plans" sub={`GET /delivery-cycles/${cycleId}/task-plans`}>
          {(plans.data ?? []).length === 0 && (
            <EmptyState title="No task plans" description="Generate a task plan to continue." />
          )}
          <ul className="ol-ws-list">
            {(plans.data ?? []).map((p) => (
              <li key={p.id} className="ol-ws-row">
                <span className="ol-id">{p.id.slice(0, 8)}</span>
                <StatusBadge status={p.status} />
                <span className="ol-body-sm ol-muted">{p.task_count} tasks</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {tab === "dag" && (
        <Panel title="Task DAG" sub="Materialized tasks or proposed plan preview">
          {dagView.isLoading && <p className="ol-body-sm ol-muted">Loading…</p>}
          {!dagView.isLoading && dagView.nodes.length === 0 && (
            <EmptyState title="No tasks in DAG" description="Generate and accept a task plan." />
          )}
          {dagView.nodes.length > 0 && (
            <>
              <div className="ol-gtool mb-3">
                <div className="ol-seg">
                  <button
                    type="button"
                    className={`ol-seg-i ${dagMode === "graph" ? "is-on" : ""}`}
                    onClick={() => setDagMode("graph")}
                  >
                    Graph
                  </button>
                  <button
                    type="button"
                    className={`ol-seg-i ${dagMode === "list" ? "is-on" : ""}`}
                    onClick={() => setDagMode("list")}
                  >
                    List
                  </button>
                </div>
              </div>
              <TaskDag
                nodes={dagView.nodes}
                edges={dagView.edges}
                selectedId={undefined}
                onSelect={() => {}}
                mode={dagMode}
                preview={dagView.isPreview}
              />
            </>
          )}
          {latestPlan && (
            <p className="ol-body-sm ol-muted mt-2">
              Latest plan status: <StatusBadge status={latestPlan.status} /> — approve{" "}
              <code>TASK_PLAN</code> in the Decision panel to accept and issue contracts.
            </p>
          )}
        </Panel>
      )}
    </StageWorkspaceFrame>
  );
}

function FeatureImplSpecs({
  featureId,
  featureKey,
  cycleId,
  scope,
  focusSpecId,
  onFocusSpec,
}: {
  featureId: string;
  featureKey: string;
  cycleId: string;
  scope: { projectId: string; cycleId: string };
  focusSpecId?: string;
  onFocusSpec: (id: string) => void;
}) {
  void scope.projectId;
  const specs = useImplementationSpecs(featureId);
  const requestApproval = useRequestImplementationSpecApproval(scope);
  const queryClient = useQueryClient();
  const focused = (specs.data ?? []).find((s) => s.id === focusSpecId);
  const focusedDetail = useQuery({
    queryKey: ["implementation-spec", focusSpecId],
    queryFn: () => fetchImplementationSpec(focusSpecId!),
    enabled: Boolean(focusSpecId && focused?.status === "PROPOSED"),
  });

  return (
    <div className="ol-ws-impl-block">
      <p className="ol-label">{featureKey}</p>
      {specs.isError && <ExceptionState status="ERROR" reason="Could not load implementation specs." />}
      {(specs.data ?? []).length === 0 && (
        <p className="ol-body-sm ol-muted">No implementation specs for this feature.</p>
      )}
      <ul className="ol-ws-list">
        {(specs.data ?? []).map((s) => (
          <li key={s.id} className="ol-ws-row">
            <button
              type="button"
              className={`ol-ws-list-btn ${focusSpecId === s.id ? "is-on" : ""}`}
              onClick={() => onFocusSpec(s.id)}
            >
              Focus
            </button>
            <span className="ol-id">v{s.version}</span>
            <StatusBadge status={s.status} />
            <StudioMutationAction
              label="Request approval"
              path={`/implementation-specs/${s.id}/approval-request`}
              body={{ delivery_cycle_id: cycleId }}
              disabled={requestApproval.isPending}
              onRun={(idem) => requestImplementationSpecApproval(s.id, cycleId, idem)}
            />
          </li>
        ))}
      </ul>
      {focused?.status === "PROPOSED" && focusedDetail.data && (
        <ImplementationSpecVersionEditor
          title={`Edit implementation spec (${featureKey})`}
          spec={focusedDetail.data}
          featureId={featureId}
          cycleId={cycleId}
          onSaved={async (newSpecId) => {
            await queryClient.prefetchQuery({
              queryKey: ["implementation-spec", newSpecId],
              queryFn: () => fetchImplementationSpec(newSpecId),
            });
            onFocusSpec(newSpecId);
          }}
        />
      )}
    </div>
  );
}
