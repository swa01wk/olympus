import { apiRequest } from "@/src/api/client";
import { newIdempotencyKey } from "@/lib/utils";

export type CommandResult = Record<string, unknown>;

export async function sendDeliveryCycleCommand(
  cycleId: string,
  commandName: string,
  expectedState: string,
  payload?: Record<string, unknown> | null,
  idempotencyKey?: string,
): Promise<CommandResult> {
  return apiRequest<CommandResult>(`/delivery-cycles/${cycleId}/commands/${commandName}`, {
    method: "POST",
    body: { expected_state: expectedState, payload: payload ?? null },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function sendTaskCommand(
  taskId: string,
  commandName: string,
  expectedState: string,
  idempotencyKey?: string,
): Promise<CommandResult> {
  return apiRequest<CommandResult>(`/tasks/${taskId}/commands/${commandName}`, {
    method: "POST",
    body: { expected_state: expectedState },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function sendApprovalDecision(
  approvalId: string,
  decision: "APPROVED" | "REJECTED" | "CHANGES_REQUESTED",
  note?: string | null,
  idempotencyKey?: string,
): Promise<unknown> {
  return apiRequest(`/approvals/${approvalId}/decision`, {
    method: "POST",
    body: { decision, note: note ?? null },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function answerClarificationCommand(clarificationId: string, answer: string) {
  return apiRequest(`/clarifications/${clarificationId}/answer`, {
    method: "POST",
    body: { answer },
  });
}

export async function createDeliveryCycleCommand(
  projectId: string,
  type: string,
  objective: string,
  repositoryId?: string | null,
  idempotencyKey?: string,
) {
  return apiRequest<{ id: string }>(`/projects/${projectId}/delivery-cycles`, {
    method: "POST",
    body: { type, objective, repository_id: repositoryId ?? null },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function cancelExecution(executionId: string, then: string = "RETURN_TO_READY") {
  return apiRequest(`/executions/${executionId}/cancel`, {
    method: "POST",
    body: { then },
  });
}

/** Unified entry for UI command flows — extend in Phase 6 dialogs. */
export async function sendCommand(
  target:
    | { kind: "delivery_cycle"; cycleId: string; command: string; expectedState: string; payload?: Record<string, unknown> | null }
    | { kind: "task"; taskId: string; command: string; expectedState: string }
    | {
        kind: "approval";
        approvalId: string;
        decision: "APPROVED" | "REJECTED" | "CHANGES_REQUESTED";
        note?: string | null;
      },
): Promise<unknown> {
  switch (target.kind) {
    case "delivery_cycle":
      return sendDeliveryCycleCommand(
        target.cycleId,
        target.command,
        target.expectedState,
        target.payload,
      );
    case "task":
      return sendTaskCommand(target.taskId, target.command, target.expectedState);
    case "approval":
      return sendApprovalDecision(target.approvalId, target.decision, target.note);
    default:
      return undefined;
  }
}
