import type { ActionRequest, ActionResult } from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

const now = "2025-09-15T12:00:00.000Z";

export function buildActions() {
  const actionAllowed = "11111111-1111-4111-8111-111111119001";
  const actionDenied = "11111111-1111-4111-8111-111111119002";
  const actionPending = "11111111-1111-4111-8111-111111119003";

  const actions: ActionRequest[] = [
    {
      id: actionAllowed,
      key: "ACT-901",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc003,
      execution_id: IDS.ex551,
      task_id: IDS.taskForge1,
      tool: "repo",
      resource: "repository",
      action: "write",
      params: { path: "app/models/ticket.py" },
      status: "EXECUTING",
      policy_decision: { decision: "ALLOW", rule_ids: ["scope.within_contract"] },
      correlation_id: "corr-act-901",
      requested_at: now,
    },
    {
      id: actionDenied,
      key: "ACT-902",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc003,
      execution_id: IDS.ex552,
      task_id: IDS.taskForge2,
      tool: "git",
      resource: "repository",
      action: "push_main",
      params: { ref: "refs/heads/main" },
      status: "DENIED",
      policy_decision: {
        decision: "DENY",
        rule_ids: ["forge.no_direct_main_push"],
        reasons: ["Implementation agents cannot push to main"],
      },
      correlation_id: "corr-act-902",
      requested_at: now,
    },
    {
      id: actionPending,
      key: "ACT-903",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc003,
      execution_id: IDS.ex552,
      task_id: IDS.taskForge2,
      tool: "deployment",
      resource: "staging",
      action: "deploy",
      params: { environment: "staging" },
      status: "PENDING_APPROVAL",
      policy_decision: {
        decision: "REQUIRE_APPROVAL",
        rule_ids: ["deployment.requires_approval"],
      },
      approval_id: IDS.approvalAction,
      correlation_id: "corr-act-903",
      requested_at: now,
    },
  ];

  const actionResults: ActionResult[] = [
    {
      id: "11111111-1111-4111-8111-111111119101",
      action_request_id: actionDenied,
      status: "FAILED",
      error: "POLICY_DENY: forge.no_direct_main_push",
    },
  ];

  return { actions, actionResults };
}
