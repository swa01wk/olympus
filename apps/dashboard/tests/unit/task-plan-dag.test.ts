import { describe, expect, it } from "vitest";
import { isMaterializedTaskId, taskPlanBodyToDag } from "@/lib/task-plan-dag";

describe("taskPlanBodyToDag", () => {
  it("maps refs and dependencies to preview nodes", () => {
    const { nodes, edges } = taskPlanBodyToDag({
      tasks: [
        { ref: "T-1", title: "First", work_type: "CODE_CHANGE" },
        { ref: "T-2", title: "Second" },
      ],
      dependencies: [{ task_ref: "T-2", depends_on_ref: "T-1" }],
    });
    expect(nodes).toHaveLength(2);
    expect(nodes[0].id).toBe("plan:T-1");
    expect(nodes[0].status).toBe("PROPOSED");
    expect(edges).toEqual([{ from: "plan:T-1", to: "plan:T-2" }]);
  });
});

describe("isMaterializedTaskId", () => {
  it("distinguishes plan preview ids", () => {
    expect(isMaterializedTaskId("01a11593-e3c4-712f-a12d-3638cbd9dc78")).toBe(true);
    expect(isMaterializedTaskId("plan:T-1")).toBe(false);
  });
});
