"use client";

import { FixtureBadge } from "@/components/states/FixtureBadge";
import type { LineageGraph } from "@/lib/contracts/entity-types";

export function LineageExplorer({ graph }: { graph: LineageGraph }) {
  return (
    <div className="space-y-3">
      <FixtureBadge />
      <p className="text-xs text-[var(--muted)]">
        {graph.direction} from {graph.root_type}:{graph.root_id.slice(0, 8)} — {graph.nodes.length} nodes
      </p>
      <ul className="max-h-96 space-y-1 overflow-y-auto font-mono text-[11px]">
        {graph.nodes.map((n) => (
          <li key={n.id} className="rounded border border-[var(--border)] px-2 py-1">
            {n.type} · {n.label ?? n.key ?? n.id.slice(0, 8)}
          </li>
        ))}
      </ul>
      <ul className="text-[10px] text-[var(--muted)]">
        {graph.edges.slice(0, 20).map((e) => (
          <li key={`${e.from}-${e.to}`}>
            {e.relation}: {String(e.from).slice(0, 6)} → {String(e.to).slice(0, 6)}
          </li>
        ))}
      </ul>
    </div>
  );
}
