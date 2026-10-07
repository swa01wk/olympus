import { mapBackendStatus } from "@/src/adapters/status";
import { laneForRecordKind } from "@/src/control-plane/lanes";
import type {
  BuildGraphInput,
  ControlPlaneGraph,
  ControlPlaneGraphEdge,
  ControlPlaneGraphNode,
} from "@/src/control-plane/graph-types";

const COLLAPSE_THRESHOLD = 6;

function nodeId(kind: string, id: string) {
  return `${kind}:${id}`;
}

function taskNodes(tasks: BuildGraphInput["tasks"]): ControlPlaneGraphNode[] {
  return tasks.map((t) => ({
    id: nodeId("Task", t.id),
    lane: laneForRecordKind("Task") ?? "work",
    kind: "Task",
    ref: t.key,
    title: t.title,
    sub: t.blocked_reason ?? undefined,
    status: mapBackendStatus(t.status).uiKey,
    backendStatus: t.status,
    materialized: true,
  }));
}

function executionNodes(execs: BuildGraphInput["executions"]): ControlPlaneGraphNode[] {
  return execs.map((e) => ({
    id: nodeId("Execution", e.id),
    lane: laneForRecordKind("Execution") ?? "exec",
    kind: "Execution",
    ref: `${e.key}${e.attempt_number != null ? ` · attempt ${e.attempt_number}` : ""}`,
    title: e.status,
    sub: e.snapshot_hash ?? undefined,
    sha: e.snapshot_hash ?? undefined,
    status: mapBackendStatus(e.status).uiKey,
    backendStatus: e.status,
    materialized: true,
  }));
}

function icNodes(ics: BuildGraphInput["integrationCandidates"]): ControlPlaneGraphNode[] {
  return ics.map((ic) => ({
    id: nodeId("IntegrationCandidate", ic.id),
    lane: laneForRecordKind("IntegrationCandidate") ?? "code",
    kind: "IntegrationCandidate",
    ref: ic.key,
    title: ic.status,
    sha: ic.integrated_sha ?? ic.base_sha,
    status: mapBackendStatus(ic.status).uiKey,
    backendStatus: ic.status,
    materialized: true,
  }));
}

function obligationNodes(
  obligations: NonNullable<BuildGraphInput["obligations"]>,
): ControlPlaneGraphNode[] {
  return obligations
    .filter((o) => o.required && o.status !== "SATISFIED")
    .map((o) => ({
      id: nodeId("Obligation", o.id),
      lane: laneForRecordKind("VerificationObligation") ?? "evidence",
      kind: "VerificationObligation",
      ref: o.subject_key,
      title: "Required evidence",
      status: o.status === "SATISFIED" ? mapBackendStatus("SATISFIED").uiKey : "missing",
      backendStatus: o.status,
      materialized: false,
      future: true,
    }));
}

function collapseLane(nodes: ControlPlaneGraphNode[], kind: string): ControlPlaneGraphNode[] {
  const ofKind = nodes.filter((n) => n.kind === kind && !n.future);
  if (ofKind.length <= COLLAPSE_THRESHOLD) return nodes.filter((n) => n.kind !== kind || n.future).concat(ofKind);

  const priority = (n: ControlPlaneGraphNode) => {
    const order = ["failed", "blocked", "checkpointed", "running", "pending", "ready", "completed"];
    const idx = order.indexOf(n.status);
    return idx >= 0 ? idx : order.length;
  };
  ofKind.sort((a, b) => priority(a) - priority(b));
  const top = ofKind[0];
  const group: ControlPlaneGraphNode = {
    id: nodeId(`${kind}Group`, kind),
    lane: top.lane,
    kind: `${kind}Group`,
    ref: `${ofKind.length} ${kind}s`,
    title: top.title,
    status: top.status,
    materialized: true,
    group: true,
    groupCount: ofKind.length,
    memberIds: ofKind.map((n) => n.id),
  };
  const rest = nodes.filter((n) => n.kind !== kind || n.future);
  return [...rest, group];
}

function defaultEdges(input: BuildGraphInput, nodes: ControlPlaneGraphNode[]): ControlPlaneGraphEdge[] {
  const edges: ControlPlaneGraphEdge[] = [];
  const taskIdSet = new Set(input.tasks.map((t) => t.id));
  for (const e of input.executions) {
    if (!taskIdSet.has(e.task_id)) continue;
    edges.push({
      id: `exec-task:${e.id}`,
      from: nodeId("Task", e.task_id),
      to: nodeId("Execution", e.id),
      rel: "ATTEMPT_OF",
      kind: "auth",
    });
  }
  const latestIc = input.integrationCandidates[input.integrationCandidates.length - 1];
  if (latestIc) {
    for (const t of input.tasks.filter((x) => x.status === "COMPLETED")) {
      edges.push({
        id: `task-ic:${t.id}:${latestIc.id}`,
        from: nodeId("Task", t.id),
        to: nodeId("IntegrationCandidate", latestIc.id),
        rel: "INTEGRATED_IN",
        kind: "auth",
      });
    }
  }
  for (const r of input.relations ?? []) {
    edges.push({
      id: `rel:${r.from}:${r.to}:${r.rel}`,
      from: r.from,
      to: r.to,
      rel: r.rel,
      kind: r.kind ?? (r.origin === "DISCOVERED" ? "inferred" : "auth"),
      confidence: r.confidence,
    });
  }
  // Drop edges to collapsed members (point to group id if needed) — keep simple: edges only between visible nodes
  const visible = new Set(nodes.map((n) => n.id));
  return edges.filter((e) => visible.has(e.from) && visible.has(e.to));
}

/**
 * Projects authoritative records into lane graph nodes and edges.
 * Does not invent future nodes except backend-expressed obligations.
 */
export function buildControlPlaneGraph(input: BuildGraphInput): ControlPlaneGraph {
  let nodes: ControlPlaneGraphNode[] = [
    ...taskNodes(input.tasks),
    ...executionNodes(input.executions),
    ...icNodes(input.integrationCandidates),
    ...obligationNodes(input.obligations ?? []),
  ];

  for (const kind of ["Task", "Execution"] as const) {
    nodes = collapseLane(nodes, kind);
  }

  const edges = defaultEdges(input, nodes);
  return { nodes, edges };
}
