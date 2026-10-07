import { describe, expect, it } from "vitest";
import { buildControlPlaneGraph } from "@/src/control-plane/build-graph";

const cycle = { id: "c1", key: "DC-1", state: "DEVELOPMENT", base_sha: "abc" };

describe("buildControlPlaneGraph", () => {
  it("materializes tasks and executions with auth edge", () => {
    const graph = buildControlPlaneGraph({
      cycle,
      tasks: [
        {
          id: "t1",
          key: "TASK-1",
          title: "Implement",
          status: "RUNNING",
          blocked_reason: null,
        },
      ],
      executions: [
        {
          id: "e1",
          key: "EX-1",
          task_id: "t1",
          status: "STARTED",
          attempt_number: 1,
          snapshot_hash: "deadbeef",
        },
      ],
      integrationCandidates: [],
    });
    expect(graph.nodes.some((n) => n.kind === "Task")).toBe(true);
    expect(graph.edges.some((e) => e.rel === "ATTEMPT_OF")).toBe(true);
  });

  it("collapses more than six tasks into a group node", () => {
    const tasks = Array.from({ length: 7 }, (_, i) => ({
      id: `t${i}`,
      key: `TASK-${i}`,
      title: `Work ${i}`,
      status: "READY",
      blocked_reason: null,
    }));
    const graph = buildControlPlaneGraph({
      cycle,
      tasks,
      executions: [],
      integrationCandidates: [],
    });
    expect(graph.nodes.some((n) => n.kind === "TaskGroup" && n.groupCount === 7)).toBe(true);
    expect(graph.nodes.filter((n) => n.kind === "Task").length).toBe(0);
  });

  it("shows future obligation nodes only from backend obligations", () => {
    const graph = buildControlPlaneGraph({
      cycle,
      tasks: [],
      executions: [],
      integrationCandidates: [],
      obligations: [
        { id: "o1", subject_key: "AC-1", status: "OPEN", required: true },
      ],
    });
    const ob = graph.nodes.find((n) => n.kind === "VerificationObligation");
    expect(ob?.future).toBe(true);
    expect(ob?.materialized).toBe(false);
  });

  it("does not invent nodes when empty", () => {
    const graph = buildControlPlaneGraph({
      cycle,
      tasks: [],
      executions: [],
      integrationCandidates: [],
    });
    expect(graph.nodes).toHaveLength(0);
  });
});
