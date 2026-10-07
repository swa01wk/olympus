import type { ControlPlaneGraphEdge, ControlPlaneGraphNode } from "@/src/control-plane/graph-types";
import type { LensId } from "@/src/control-plane/lanes";
import type { AttentionItem } from "@/src/control-plane/attention";

const BLOCKER_STATUSES = new Set(["blocked", "failed", "missing", "not-eligible", "checkpointed", "approval-pending"]);

export function highlightNodeIds(
  lens: LensId,
  nodes: ControlPlaneGraphNode[],
  edges: ControlPlaneGraphEdge[],
  selectedId: string | undefined,
  attention: AttentionItem[],
): Set<string> | null {
  if (lens === "lifecycle" || !selectedId) {
    if (lens === "blockers") return blockerHighlight(nodes, edges, selectedId, attention);
    return null;
  }
  if (lens === "trace") {
    return traceHighlight(edges, selectedId);
  }
  if (lens === "impact") {
    return new Set(nodes.filter((n) => n.impact).map((n) => n.id));
  }
  if (lens === "blockers") {
    return blockerHighlight(nodes, edges, selectedId, attention);
  }
  return null;
}

function traceHighlight(edges: ControlPlaneGraphEdge[], selectedId: string): Set<string> {
  const set = new Set<string>([selectedId]);
  for (const e of edges) {
    if (e.from === selectedId) set.add(e.to);
    if (e.to === selectedId) set.add(e.from);
  }
  return set;
}

function blockerHighlight(
  nodes: ControlPlaneGraphNode[],
  edges: ControlPlaneGraphEdge[],
  selectedId: string | undefined,
  attention: AttentionItem[],
): Set<string> {
  const set = new Set<string>();
  for (const n of nodes) {
    if (BLOCKER_STATUSES.has(n.status)) set.add(n.id);
  }
  if (selectedId) set.add(selectedId);
  for (const e of edges) {
    if (set.has(e.from) && set.has(e.to)) continue;
    if (set.has(e.from)) set.add(e.to);
    if (set.has(e.to)) set.add(e.from);
  }
  if (attention.length && nodes.length) {
    const first = nodes.find((n) => BLOCKER_STATUSES.has(n.status));
    if (first) set.add(first.id);
  }
  return set;
}
