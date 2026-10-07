import { apiFormRequest, apiRequest } from "@/src/api/client";
import type { RunnableProposalRoute } from "@/src/api/proposal-routes";
import { newIdempotencyKey } from "@/lib/utils";
import type { DeliveryCycle } from "@/src/api/types/core";
import type { FeatureSpecBody } from "@/src/api/types/product-model";
import type { OrchestratorSession } from "@/src/api/types/orchestrator";
import type { RegisterRepositoryInput, Repository } from "@/src/api/types/repository";

export type CommandResult = Record<string, unknown>;

export type UploadProductSourceInput =
  | { file: File }
  | {
      title: string;
      text: string;
      lineage_key?: string;
      source_type?: string;
    };

export type RequestApprovalBody = {
  approval_type: string;
  subject_type: string;
  subject_id: string;
  subject_version: number;
  subject_hash: string;
};

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

export async function answerClarification(clarificationId: string, answer: string) {
  return apiRequest(`/clarifications/${clarificationId}/answer`, {
    method: "POST",
    body: { answer },
  });
}

/** @deprecated Use `answerClarification` */
export async function answerClarificationCommand(clarificationId: string, answer: string) {
  return answerClarification(clarificationId, answer);
}

export async function createDeliveryCycle(
  projectId: string,
  body: { type: string; objective: string; repository_id?: string | null },
  idempotencyKey?: string,
) {
  return apiRequest<DeliveryCycle>(`/projects/${projectId}/delivery-cycles`, {
    method: "POST",
    body,
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function registerRepository(
  projectId: string,
  input: RegisterRepositoryInput,
  idempotencyKey?: string,
) {
  return apiRequest<Repository>(`/projects/${projectId}/repositories`, {
    method: "POST",
    body: {
      name: input.name,
      provider: input.provider,
      remote_url: input.remote_url,
      default_branch: input.default_branch ?? null,
      credential_ref: input.credential_ref ?? "none:",
      source_type: "EXTERNAL_CLONE",
    },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function putSecret(name: string, value: string, idempotencyKey?: string) {
  return apiRequest<{ credential_ref: string }>(`/secrets/${name}`, {
    method: "PUT",
    body: { value },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function retryMaterialization(repositoryId: string, idempotencyKey?: string) {
  return apiRequest<Repository>(`/repositories/${repositoryId}/commands/retry_materialization`, {
    method: "POST",
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

/** @deprecated Use `createDeliveryCycle` */
export async function createDeliveryCycleCommand(
  projectId: string,
  type: string,
  objective: string,
  repositoryId?: string | null,
  idempotencyKey?: string,
) {
  return createDeliveryCycle(
    projectId,
    { type, objective, repository_id: repositoryId ?? null },
    idempotencyKey,
  );
}

export async function cancelExecution(executionId: string, then: string = "RETURN_TO_READY") {
  return apiRequest(`/executions/${executionId}/cancel`, {
    method: "POST",
    body: { then },
  });
}

export async function uploadProductSource(
  projectId: string,
  cycleId: string,
  input: UploadProductSourceInput,
  idempotencyKey?: string,
) {
  const qs = new URLSearchParams({ delivery_cycle_id: cycleId });
  const path = `/projects/${projectId}/sources?${qs}`;
  if ("file" in input) {
    const form = new FormData();
    form.append("file", input.file);
    return apiFormRequest<{ result: { product_source_id: string } }>(path, form, {
      idempotencyKey,
    });
  }
  return apiRequest<{ result: { product_source_id: string } }>(path, {
    method: "POST",
    body: {
      title: input.title,
      text: input.text,
      lineage_key: input.lineage_key ?? "default",
      source_type: input.source_type ?? "PRD",
    },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function decomposeSource(sourceId: string, cycleId: string, idempotencyKey?: string) {
  return apiRequest<CommandResult>(`/sources/${sourceId}/decompose`, {
    method: "POST",
    body: { delivery_cycle_id: cycleId },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function deriveSource(sourceId: string, cycleId: string, idempotencyKey?: string) {
  return apiRequest<CommandResult>(`/sources/${sourceId}/derive`, {
    method: "POST",
    body: { delivery_cycle_id: cycleId },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function createFeatureSpecVersion(
  featureId: string,
  body: FeatureSpecBody,
  idempotencyKey?: string,
) {
  return apiRequest<{ spec_id: string; version: string }>(`/features/${featureId}/specs`, {
    method: "POST",
    body: { body },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function requestScopeApproval(
  cycleId: string,
  featureSpecIds: string[],
  idempotencyKey?: string,
) {
  return apiRequest<CommandResult>(`/delivery-cycles/${cycleId}/scope/approval-request`, {
    method: "POST",
    body: { feature_spec_ids: featureSpecIds },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function proposeArchitecture(cycleId: string, idempotencyKey?: string) {
  return apiRequest<{ architecture_id?: string; execution_id?: string }>(
    `/delivery-cycles/${cycleId}/architecture/propose`,
    { method: "POST", idempotencyKey: idempotencyKey ?? newIdempotencyKey() },
  );
}

export async function requestArchitectureApproval(
  architectureId: string,
  cycleId: string,
  idempotencyKey?: string,
) {
  return apiRequest<{ approval_id: string }>(`/architectures/${architectureId}/approval-request`, {
    method: "POST",
    body: { delivery_cycle_id: cycleId },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function generateImplementationSpecs(cycleId: string, idempotencyKey?: string) {
  return apiRequest<{ tasks: unknown }>(
    `/delivery-cycles/${cycleId}/implementation-specs/generate`,
    { method: "POST", idempotencyKey: idempotencyKey ?? newIdempotencyKey() },
  );
}

export async function requestImplementationSpecApproval(
  specId: string,
  cycleId: string,
  idempotencyKey?: string,
) {
  return apiRequest<{ approval_id: string }>(`/implementation-specs/${specId}/approval-request`, {
    method: "POST",
    body: { delivery_cycle_id: cycleId },
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function generateTaskPlan(cycleId: string, idempotencyKey?: string) {
  return apiRequest<{ execution_id?: string; task_plan_id?: string }>(
    `/delivery-cycles/${cycleId}/task-plan/generate`,
    { method: "POST", idempotencyKey: idempotencyKey ?? newIdempotencyKey() },
  );
}

export async function rerunChangeInterpretation(cycleId: string, idempotencyKey?: string) {
  return apiRequest<Record<string, string>>(
    `/delivery-cycles/${cycleId}/change-interpretation/rerun`,
    { method: "POST", idempotencyKey: idempotencyKey ?? newIdempotencyKey() },
  );
}

export async function runImpactAssessment(
  cycleId: string,
  body: { spec_delta_id?: string; seed_stable_keys?: string[]; index_version_id?: string },
  idempotencyKey?: string,
) {
  return apiRequest<Record<string, string>>(`/delivery-cycles/${cycleId}/impact-assessments`, {
    method: "POST",
    body,
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function acceptTaskPlan(planId: string, idempotencyKey?: string) {
  return apiRequest<{ id: string; status: string }>(`/task-plans/${planId}/commands/accept`, {
    method: "POST",
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function requestApproval(
  cycleId: string,
  body: RequestApprovalBody,
  idempotencyKey?: string,
) {
  return apiRequest<{ id: string }>(`/delivery-cycles/${cycleId}/approvals`, {
    method: "POST",
    body,
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function createRelease(cycleId: string, idempotencyKey?: string) {
  return apiRequest<{
    id: string;
    key: string;
    status: string;
    delivery_cycle_id: string;
  }>(`/delivery-cycles/${cycleId}/release`, {
    method: "POST",
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function approveRelease(releaseId: string, idempotencyKey?: string) {
  return apiRequest<{ id: string; status: string }>(`/releases/${releaseId}/approve`, {
    method: "POST",
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function executeRelease(releaseId: string, idempotencyKey?: string) {
  return apiRequest<{ execution_id: string }>(`/releases/${releaseId}/execute`, {
    method: "POST",
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
  });
}

export async function createOrchestratorSession(body: {
  project_id?: string | null;
  delivery_cycle_id?: string | null;
}) {
  return apiRequest<OrchestratorSession>("/orchestrator/sessions", { method: "POST", body });
}

export async function postOrchestratorTurn(sessionId: string, message: string) {
  return apiRequest<{ execution_id: string }>(`/orchestrator/sessions/${sessionId}/turns`, {
    method: "POST",
    body: { message },
  });
}

export async function executeRunnableProposal(
  route: RunnableProposalRoute,
  idempotencyKey?: string,
) {
  const qs = route.query ? `?${new URLSearchParams(route.query)}` : "";
  return apiRequest<Record<string, unknown>>(`${route.path}${qs}`, {
    method: "POST",
    body: route.body ?? undefined,
    idempotencyKey: idempotencyKey ?? newIdempotencyKey(),
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
