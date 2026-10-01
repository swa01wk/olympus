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
import type { Task } from "@/lib/contracts/entity-types";

export function TaskDagGraph({
  nodes: tasks,
  edges: deps,
}: {
  nodes: Task[];
  edges: { task_id: string; depends_on_task_id: string; kind: string }[];
}) {
  const { nodes, edges } = useMemo(() => {
    const n: Node[] = tasks.map((t, i) => ({
      id: t.id,
      data: { label: `${t.key}\n${t.status}` },
      position: { x: (i % 3) * 220, y: Math.floor(i / 3) * 100 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    }));
    const e: Edge[] = deps.map((d) => ({
      id: `${d.depends_on_task_id}-${d.task_id}`,
      source: d.depends_on_task_id,
      target: d.task_id,
      label: d.kind,
    }));
    return { nodes: n, edges: e };
  }, [tasks, deps]);

  return (
    <div className="h-[420px] rounded border border-[var(--border)]">
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
