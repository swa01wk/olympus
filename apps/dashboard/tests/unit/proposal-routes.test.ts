import { describe, expect, it } from "vitest";
import { routeForProposal } from "@/src/api/proposal-routes";
import type { OrchestratorProposal } from "@/src/api/types/orchestrator";

const ctx = { projectId: "proj-1", cycleId: "cycle-2", cycleState: "DISCOVERY" };

function proposal(command: string, args: Record<string, unknown> = {}): OrchestratorProposal {
  return { command, target_ref: "ref-1", args, rationale: "test" };
}

describe("routeForProposal §6", () => {
  it("delivery_cycle.transition", () => {
    const route = routeForProposal(proposal("delivery_cycle.transition", { command_name: "start_product_modeling" }), ctx);
    expect(route).toEqual({
      method: "POST",
      path: "/delivery-cycles/cycle-2/commands/start_product_modeling",
      body: { expected_state: "DISCOVERY", payload: null },
    });
  });

  it("create_delivery_cycle", () => {
    const route = routeForProposal(
      proposal("create_delivery_cycle", {
        type: "GREENFIELD_BUILD",
        objective: "Build",
      }),
      ctx,
    );
    expect(route).toMatchObject({
      path: "/projects/proj-1/delivery-cycles",
      body: { type: "GREENFIELD_BUILD", objective: "Build", repository_id: null },
    });
  });

  it("ingest_product_source", () => {
    const route = routeForProposal(
      proposal("ingest_product_source", { title: "PRD", text: "hello" }),
      ctx,
    );
    expect(route).toMatchObject({
      path: "/projects/proj-1/sources",
      query: { delivery_cycle_id: "cycle-2" },
    });
  });

  it("decompose_source", () => {
    const route = routeForProposal(proposal("decompose_source", { source_id: "src-9" }), ctx);
    expect(route).toMatchObject({
      path: "/sources/src-9/decompose",
      body: { delivery_cycle_id: "cycle-2" },
    });
  });

  it("request_scope_approval", () => {
    const route = routeForProposal(
      proposal("request_scope_approval", { feature_spec_ids: ["s1", "s2"] }),
      ctx,
    );
    expect(route).toMatchObject({
      path: "/delivery-cycles/cycle-2/scope/approval-request",
      body: { feature_spec_ids: ["s1", "s2"] },
    });
  });

  it("approval.request", () => {
    const route = routeForProposal(
      proposal("approval.request", {
        approval_type: "SCOPE",
        subject_type: "scope_set",
        subject_id: "sub-1",
        subject_version: 1,
        subject_hash: "abc",
      }),
      ctx,
    );
    expect(route).toMatchObject({ path: "/delivery-cycles/cycle-2/approvals" });
  });

  it("task.command", () => {
    const route = routeForProposal(
      proposal("task.command", {
        task_id: "task-3",
        command_name: "mark_ready",
        expected_state: "DRAFT",
      }),
      ctx,
    );
    expect(route).toMatchObject({
      path: "/tasks/task-3/commands/mark_ready",
      body: { expected_state: "DRAFT" },
    });
  });

  it("create_task", () => {
    const route = routeForProposal(
      proposal("create_task", { title: "Work", work_type: "CODE" }),
      ctx,
    );
    expect(route).toMatchObject({ path: "/delivery-cycles/cycle-2/tasks" });
  });

  it("intake_change_request", () => {
    const route = routeForProposal(
      proposal("intake_change_request", { title: "Change", description: "Details" }),
      ctx,
    );
    expect(route).toMatchObject({ path: "/projects/proj-1/change-requests" });
  });

  it("intake_defect", () => {
    const route = routeForProposal(
      proposal("intake_defect", { title: "Bug", description: "Broken" }),
      ctx,
    );
    expect(route).toMatchObject({ path: "/projects/proj-1/defects" });
  });

  it("approval.decide is not runnable", () => {
    const route = routeForProposal(proposal("approval.decide"), ctx);
    expect(route).toEqual({
      notRunnable: "Approvals must be decided in the workspace Decision panel",
    });
  });

  it("unknown command is not runnable", () => {
    const route = routeForProposal(proposal("unknown.command"), ctx);
    expect(route).toEqual({ notRunnable: "Not runnable from chat: unknown.command" });
  });
});
