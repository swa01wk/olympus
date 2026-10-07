import type { TaskDagEdge, TaskDagNode } from "@/src/api/resources";

export type TaskPlanBody = {
  tasks?: Array<{
    ref: string;
    title: string;
    work_type?: string;
  }>;
  dependencies?: Array<{
    task_ref: string;
    depends_on_ref: string;
  }>;
};

export function taskPlanBodyToDag(body: TaskPlanBody): { nodes: TaskDagNode[]; edges: TaskDagEdge[] } {
  const tasks = body.tasks ?? [];
  const refToId = new Map(tasks.map((t) => [t.ref, `plan:${t.ref}`]));
  const nodes: TaskDagNode[] = tasks.map((t) => ({
    id: refToId.get(t.ref)!,
    key: t.ref,
    title: t.title,
    status: "PROPOSED",
    work_type: t.work_type ?? "CODE_CHANGE",
  }));
  const edges: TaskDagEdge[] = [];
  for (const d of body.dependencies ?? []) {
    const from = refToId.get(d.depends_on_ref);
    const to = refToId.get(d.task_ref);
    if (from && to) edges.push({ from, to });
  }
  return { nodes, edges };
}

export function isMaterializedTaskId(taskId: string): boolean {
  return !taskId.startsWith("plan:");
}
