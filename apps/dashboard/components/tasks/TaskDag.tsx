"use client";

import { StatusBadge } from "@/components/primitives";
import type { TaskDagEdge, TaskDagNode } from "@/src/api/resources";
import { cn } from "@/lib/utils";
import { useMemo } from "react";

function layers(nodes: TaskDagNode[], edges: TaskDagEdge[]): TaskDagNode[][] {
  const idSet = new Set(nodes.map((n) => n.id));
  const indeg = new Map<string, number>();
  for (const n of nodes) indeg.set(n.id, 0);
  for (const e of edges) {
    if (!idSet.has(e.from) || !idSet.has(e.to)) continue;
    indeg.set(e.to, (indeg.get(e.to) ?? 0) + 1);
  }
  const remaining = new Set(nodes.map((n) => n.id));
  const out: TaskDagNode[][] = [];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  while (remaining.size) {
    const layer = [...remaining].filter((id) => (indeg.get(id) ?? 0) === 0);
    if (!layer.length) {
      out.push([...remaining].map((id) => byId.get(id)!));
      break;
    }
    out.push(layer.map((id) => byId.get(id)!));
    for (const id of layer) {
      remaining.delete(id);
      for (const e of edges) {
        if (e.from === id && remaining.has(e.to)) {
          indeg.set(e.to, (indeg.get(e.to) ?? 1) - 1);
        }
      }
    }
  }
  return out;
}

export function TaskDag({
  nodes,
  edges,
  selectedId,
  onSelect,
  mode,
  preview = false,
}: {
  nodes: TaskDagNode[];
  edges: TaskDagEdge[];
  selectedId?: string;
  onSelect: (id: string) => void;
  mode: "graph" | "list";
  /** Proposed task-plan nodes (not yet materialized as Task rows). */
  preview?: boolean;
}) {
  const stacked = useMemo(() => layers(nodes, edges), [nodes, edges]);
  const waiting = useMemo(() => {
    const set = new Set<string>();
    for (const e of edges) {
      const from = nodes.find((n) => n.id === e.from);
      if (from && from.status !== "COMPLETE" && from.status !== "DONE") {
        set.add(`${e.from}-${e.to}`);
      }
    }
    return set;
  }, [edges, nodes]);

  if (mode === "list") {
    return (
      <ul className="flex flex-col gap-2">
        {nodes.map((n) => (
          <li key={n.id}>
            <button
              type="button"
              className={cn(
                "ol-ls w-full text-left",
                selectedId === n.id && "is-on",
                preview && "opacity-90",
              )}
              onClick={() => onSelect(n.id)}
            >
              <span className="ol-ls-code">{n.key}</span>
              <span className="ol-ls-name">{n.title}</span>
              <StatusBadge status={n.status} />
            </button>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="flex flex-col gap-16 py-2">
      {stacked.map((layer, li) => (
        <div key={li} className="flex flex-wrap gap-3 justify-center">
          {layer.map((n) => (
            <button
              key={n.id}
              type="button"
              className={cn(
                "ol-node min-w-[160px] text-left",
                selectedId === n.id && "is-sel",
                preview && "is-future",
              )}
              onClick={() => onSelect(n.id)}
            >
              <div className="ol-node-k">{n.key}</div>
              <div className="ol-node-t">{n.title}</div>
              <StatusBadge status={n.status} />
            </button>
          ))}
        </div>
      ))}
      {edges.length > 0 && (
        <p className="text-xs ol-muted text-center">
          Dotted dependency edges mark tasks still waiting on upstream completion (
          {waiting.size} waiting).
        </p>
      )}
    </div>
  );
}
