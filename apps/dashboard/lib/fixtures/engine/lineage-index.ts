import type { LineageEdge, LineageGraph, LineageNode } from "@/lib/contracts/entity-types";
import type { World } from "./world";

export function queryLineage(
  world: World,
  params: {
    root_type: string;
    root_id: string;
    direction: "FORWARD" | "REVERSE";
    depth?: number;
  },
): LineageGraph {
  const depth = params.depth ?? 3;
  const nodes = new Map<string, LineageNode>();
  const edges: LineageEdge[] = [];

  const addNode = (n: LineageNode) => {
    nodes.set(n.id, n);
  };

  addNode({
    type: params.root_type,
    id: params.root_id,
    label: params.root_id.slice(0, 8),
  });

  const taskById = new Map(world.tasks.map((t) => [t.id, t]));
  const exByTask = new Map<string, typeof world.executions>();
  for (const ex of world.executions) {
    const list = exByTask.get(ex.task_id) ?? [];
    list.push(ex);
    exByTask.set(ex.task_id, list);
  }

  for (const link of world.specCodeLinks) {
    if (params.direction === "REVERSE" && link.entity_stable_key.includes("TicketService")) {
      addNode({
        type: "FEATURE_SPEC",
        id: link.spec_id,
        key: link.spec_lineage_key,
        label: link.spec_lineage_key ?? "FeatureSpec",
        origin: link.origin,
        confidence: link.confidence ?? undefined,
      });
      edges.push({
        from: link.spec_id,
        to: params.root_id,
        relation: link.relation,
        origin: link.origin,
        confidence: link.confidence ?? undefined,
      });
    }
  }

  for (const t of world.tasks) {
    addNode({ type: "TASK", id: t.id, key: t.key, label: t.title });
    if (params.direction === "FORWARD" && t.key === "TASK-221") {
      const exs = exByTask.get(t.id) ?? [];
      for (const ex of exs) {
        addNode({ type: "EXECUTION", id: ex.id, key: ex.key, label: ex.key });
        edges.push({ from: t.id, to: ex.id, relation: "EXECUTES" });
        const cc = world.candidateCommits.find((c) => c.execution_id === ex.id);
        if (cc) {
          edges.push({ from: ex.id, to: params.root_id, relation: "PRODUCES" });
        }
      }
    }
  }

  if (nodes.size <= 1 && world.sampleLineage.nodes.length) {
    return { ...world.sampleLineage, direction: params.direction, root_id: params.root_id, root_type: params.root_type };
  }

  return {
    root_type: params.root_type,
    root_id: params.root_id,
    direction: params.direction,
    nodes: [...nodes.values()].slice(0, 150),
    edges: edges.slice(0, 200),
  };
}
