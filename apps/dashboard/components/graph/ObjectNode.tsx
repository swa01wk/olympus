"use client";

import { StatusBadge } from "@/components/primitives";
import { presentationForUiKey } from "@/src/adapters/status";
import type { ControlPlaneGraphNode } from "@/src/control-plane/graph-types";
import { cn } from "@/lib/utils";
import type { Ref } from "react";

export function ObjectNode({
  node,
  selected,
  dim,
  onClick,
  innerRef,
}: {
  node: ControlPlaneGraphNode;
  selected?: boolean;
  dim?: boolean;
  onClick?: () => void;
  innerRef?: Ref<HTMLButtonElement>;
}) {
  const meta = presentationForUiKey(node.status);
  const future = node.future === true;
  return (
    <button
      type="button"
      ref={innerRef}
      className={cn(
        "ol-node",
        `ol-nt-${meta.tone}`,
        future && "is-future",
        selected && "is-sel",
        dim && "is-dim",
        node.group && "is-stack",
      )}
      onClick={onClick}
      aria-pressed={selected}
      aria-label={`${node.kind} ${node.ref}: ${node.title}. ${meta.label}`}
    >
      <span className="ol-node-k">{node.kind}</span>
      <span className="ol-node-id">{node.ref}</span>
      <span className="ol-node-t">{node.title}</span>
      {node.sub && <span className="ol-node-sub">{node.sub}</span>}
      <span className="ol-node-f">
        <StatusBadge status={node.status} size="sm" />
        {node.groupCount != null && <span className="ol-node-count">×{node.groupCount}</span>}
      </span>
    </button>
  );
}
