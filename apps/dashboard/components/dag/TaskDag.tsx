"use client";

import { useMemo } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  type Edge,
  type Node,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { TaskNode, type TaskNodeData } from "@/components/dag/TaskNode";
import { useSimpleElkLayout } from "@/components/dag/useSimpleElkLayout";
import type { Task } from "@/lib/contracts/entity-types";

const nodeTypes = { taskNode: TaskNode };

export function TaskDag({
  tasks,
  edges: deps,
  executionKeyByTaskId,
  selectedTaskId,
  onSelectTask,
}: {
  tasks: Task[];
  edges: { task_id: string; depends_on_task_id: string; kind: string }[];
  executionKeyByTaskId?: Record<string, string | undefined>;
  selectedTaskId?: string | null;
  onSelectTask: (taskId: string) => void;
}) {
  const execByTask = useMemo(() => {
    const m = new Map<string, string>();
    Object.entries(executionKeyByTaskId ?? {}).forEach(([tid, key]) => {
      if (key) m.set(tid, key);
    });
    return m;
  }, [executionKeyByTaskId]);

  const depCount = useMemo(() => {
    const c = new Map<string, number>();
    deps.forEach((d) => c.set(d.task_id, (c.get(d.task_id) ?? 0) + 1));
    return c;
  }, [deps]);

  const { baseNodes, baseEdges, signature } = useMemo(() => {
    const baseNodes: Node<TaskNodeData>[] = tasks.map((t) => ({
      id: t.id,
      type: "taskNode",
      data: {
        key: t.key,
        title: t.title,
        status: t.status,
        executionKey: execByTask.get(t.id),
        dependencyCount: depCount.get(t.id) ?? 0,
      },
      position: { x: 0, y: 0 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      selected: t.id === selectedTaskId,
    }));
    const baseEdges: Edge[] = deps.map((d) => ({
      id: `${d.depends_on_task_id}-${d.task_id}`,
      source: d.depends_on_task_id,
      target: d.task_id,
      label: d.kind,
      labelStyle: { fill: "#8b93a1", fontSize: 10 },
      labelBgStyle: { fill: "#12151a", fillOpacity: 0.9 },
    }));
    const signature = `${tasks.map((t) => `${t.id}:${t.status}`).join("|")}|${deps.length}`;
    return { baseNodes, baseEdges, signature };
  }, [tasks, deps, selectedTaskId, depCount, execByTask]);

  const { layoutNodes, layoutEdges } = useSimpleElkLayout(baseNodes, baseEdges, signature);

  return (
    <div className="h-[480px] rounded border border-[var(--border)]">
      <ReactFlow
        nodes={layoutNodes}
        edges={layoutEdges}
        nodeTypes={nodeTypes}
        fitView
        onNodeClick={(_, n) => onSelectTask(n.id)}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
