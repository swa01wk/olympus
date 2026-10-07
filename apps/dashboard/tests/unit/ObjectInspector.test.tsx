import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ObjectInspector } from "@/components/inspector/ObjectInspector";
import type { ControlPlaneGraphNode } from "@/src/control-plane/graph-types";

const node: ControlPlaneGraphNode = {
  id: "Task:task-1",
  kind: "Task",
  ref: "TASK-1",
  title: "Implement feature",
  lane: "work",
  status: "ready",
  backendStatus: "READY",
  materialized: true,
};

describe("ObjectInspector", () => {
  it("shows why-unavailable exceptional state without why payload", () => {
    render(
      <ObjectInspector
        node={node}
        edges={[]}
        nodesById={new Map([[node.id, node]])}
        commands={[]}
        projectId="p1"
        cycleId="c1"
        lens="lifecycle"
        onSelect={() => {}}
      />,
    );
    expect(screen.getByText(/Why unavailable/i)).toBeInTheDocument();
    expect(screen.getByText(/TASK-1/)).toBeInTheDocument();
  });
});
