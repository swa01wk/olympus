"use client";

import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { StatusBadge } from "@/components/status/StatusBadge";

export type TaskNodeData = {
  key: string;
  title: string;
  status: string;
  capability?: string;
  executionKey?: string;
  risk?: string;
  dependencyCount: number;
};

export function TaskNode({ data, selected }: NodeProps<Node<TaskNodeData>>) {
  return (
    <div
      className={`min-w-[160px] rounded border bg-[var(--raised)] px-2 py-2 text-xs shadow-md ${
        selected ? "border-amber-400" : "border-[var(--border)]"
      } ${data.status === "RUNNING" ? "ring-1 ring-sky-500/50" : ""}`}
      aria-label={`Task ${data.key} ${data.status}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-[var(--muted)]" />
      <div className="font-mono text-amber-300">{data.key}</div>
      <div className="mt-1 line-clamp-2 text-[11px]">{data.title}</div>
      <div className="mt-2 flex flex-wrap gap-1">
        <StatusBadge value={data.status} kind="task" />
        {data.capability && <span className="text-[10px] text-[var(--muted)]">{data.capability}</span>}
      </div>
      {data.executionKey && (
        <div className="mt-1 font-mono text-[10px] text-sky-300">{data.executionKey}</div>
      )}
      <div className="mt-1 text-[10px] text-[var(--muted)]">deps: {data.dependencyCount}</div>
      <Handle type="source" position={Position.Right} className="!bg-[var(--muted)]" />
    </div>
  );
}
