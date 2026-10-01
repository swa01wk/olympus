"use client";

import { useEffect, useState } from "react";
import type { Edge, Node } from "@xyflow/react";

/** Lightweight layered layout (elkjs sync) — memoized by signature in caller. */
export function useSimpleElkLayout(
  nodes: Node[],
  edges: Edge[],
  signature: string,
): { layoutNodes: Node[]; layoutEdges: Edge[]; ready: boolean } {
  const [out, setOut] = useState<{ layoutNodes: Node[]; layoutEdges: Edge[]; ready: boolean }>({
    layoutNodes: nodes,
    layoutEdges: edges,
    ready: false,
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ELK = (await import("elkjs/lib/elk.bundled.js")).default;
        const elk = new ELK();
        const graph = {
          id: "root",
          layoutOptions: {
            "elk.algorithm": "layered",
            "elk.direction": "RIGHT",
            "elk.spacing.nodeNode": "48",
            "elk.layered.spacing.nodeNodeBetweenLayers": "64",
          },
          children: nodes.map((n) => ({
            id: n.id,
            width: 180,
            height: 100,
          })),
          edges: edges.map((e) => ({
            id: e.id,
            sources: [e.source],
            targets: [e.target],
          })),
        };
        const laid = await elk.layout(graph);
        if (cancelled) return;
        const pos = new Map(laid.children?.map((c) => [c.id, { x: c.x ?? 0, y: c.y ?? 0 }]) ?? []);
        setOut({
          layoutNodes: nodes.map((n) => ({
            ...n,
            position: pos.get(n.id) ?? n.position,
          })),
          layoutEdges: edges,
          ready: true,
        });
      } catch {
        if (!cancelled) setOut({ layoutNodes: nodes, layoutEdges: edges, ready: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [signature, nodes, edges]);

  return out;
}
