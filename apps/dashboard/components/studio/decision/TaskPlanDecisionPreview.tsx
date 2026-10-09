"use client";

import { Label } from "@/components/primitives";
import { TaskDag } from "@/components/tasks/TaskDag";
import { taskPlanBodyToDag, type TaskPlanBody } from "@/lib/task-plan-dag";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";
import { fetchTaskPlan } from "@/src/api/resources";

export function TaskPlanDecisionPreview({ planId }: { planId: string }) {
  const plan = useQuery({
    queryKey: queryKeys.taskPlans.detail(planId),
    queryFn: () => fetchTaskPlan(planId),
  });
  if (plan.isLoading) {
    return <p className="ol-body-sm ol-muted">Loading task plan…</p>;
  }
  if (plan.isError || !plan.data) {
    return <p className="ol-body-sm ol-muted">Could not load task plan.</p>;
  }
  const body = (plan.data.body ?? {}) as TaskPlanBody;
  const tasks = Array.isArray(body.tasks) ? body.tasks : [];
  const dependencies = Array.isArray(body.dependencies) ? body.dependencies : [];
  const risks = Array.isArray(body.risks) ? body.risks : [];
  const dag = taskPlanBodyToDag({ tasks, dependencies });
  return (
    <div className="ol-decision-subject">
      <div>
        <Label>Plan status</Label>
        <div>{plan.data.status}</div>
      </div>
      <div>
        <Label>Tasks ({tasks.length})</Label>
        <ul className="ol-ws-list">
          {tasks.map((t, i) => (
            <li key={t.ref ?? i} className="ol-ws-row">
              <span className="ol-id">{t.ref}</span>
              <span className="ol-body-sm">{t.title ?? "—"}</span>
              {t.estimated_size && (
                <span className="ol-body-sm ol-muted">size {t.estimated_size}</span>
              )}
              <span className="ol-body-sm ol-muted">
                scope: {(t.allowed_scope ?? []).length > 0 ? t.allowed_scope!.join(", ") : "—"}
              </span>
              {(t.ac_refs ?? []).length > 0 && (
                <span className="ol-body-sm ol-muted">ACs: {t.ac_refs!.join(", ")}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <Label>Dependencies (prerequisite → dependent)</Label>
        {dependencies.length === 0 ? (
          <p className="ol-body-sm ol-muted">No dependencies — tasks can run in parallel.</p>
        ) : (
          <ol className="ol-ws-bullets" aria-label="Task dependencies">
            {dependencies.map((d) => (
              <li key={`${d.depends_on_ref}->${d.task_ref}`}>
                <span className="ol-id">
                  {d.depends_on_ref} → {d.task_ref}
                </span>
                {d.reason && <span className="ol-muted"> — {d.reason}</span>}
              </li>
            ))}
          </ol>
        )}
        {dag.nodes.length > 0 && (
          <TaskDag nodes={dag.nodes} edges={dag.edges} onSelect={() => {}} mode="graph" preview />
        )}
      </div>
      <div>
        <Label>Risks ({risks.length})</Label>
        {risks.length === 0 ? (
          <p className="ol-body-sm ol-muted">No plan-level risks recorded.</p>
        ) : (
          <ul className="ol-ws-bullets">
            {risks.map((r, i) => (
              <li key={`${i}-${r.description}`}>
                <strong>{r.severity}</strong> {r.description}
                {(r.related_refs ?? []).length > 0 && (
                  <span className="ol-muted"> ({r.related_refs!.join(", ")})</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
