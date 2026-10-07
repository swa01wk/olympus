import { apiRequest } from "@/src/api/client";
import type {
  ControlPlaneSummaryView,
  CycleOverviewView,
  DeliveryCycle,
  DomainEventPayload,
  Execution,
  InboxItem,
  IntegrationCandidate,
  Project,
  Task,
  TransitionPreview,
  VerificationObligation,
} from "@/src/api/types/core";

export function fetchActorMe() {
  return apiRequest<{ actor_id: string; kind: string; name: string; roles: string[] }>(
    "/actors/me",
  );
}

export function fetchProjects() {
  return apiRequest<Project[]>("/projects");
}

export function fetchProject(projectId: string) {
  return apiRequest<Project>(`/projects/${projectId}`);
}

export function fetchDeliveryCycles(projectId: string) {
  return apiRequest<DeliveryCycle[]>(`/projects/${projectId}/delivery-cycles`);
}

export function fetchDeliveryCycle(cycleId: string) {
  return apiRequest<DeliveryCycle>(`/delivery-cycles/${cycleId}`);
}

export function fetchNextTransitions(cycleId: string) {
  return apiRequest<TransitionPreview[]>(`/delivery-cycles/${cycleId}/next-transitions`);
}

export function fetchCycleOverview(cycleId: string) {
  return apiRequest<CycleOverviewView>(`/views/delivery-cycles/${cycleId}/overview`);
}

export function fetchControlPlaneSummary(cycleId: string) {
  return apiRequest<ControlPlaneSummaryView>(`/views/delivery-cycles/${cycleId}/control-plane`);
}

export function fetchProjectOverview(projectId: string) {
  return apiRequest<Record<string, unknown>>(`/views/projects/${projectId}/overview`);
}

export function fetchInbox() {
  return apiRequest<InboxItem[]>("/views/inbox");
}

export function fetchTasks(cycleId: string) {
  return apiRequest<Task[]>(`/delivery-cycles/${cycleId}/tasks`);
}

export function fetchTask(taskId: string) {
  return apiRequest<Task>(`/tasks/${taskId}`);
}

export type TaskDagNode = {
  id: string;
  key: string;
  title: string;
  status: string;
  work_type: string;
};

export type TaskDagEdge = { from: string; to: string };

export function fetchTaskDag(cycleId: string) {
  return apiRequest<{ nodes: TaskDagNode[]; edges: TaskDagEdge[] }>(`/views/tasks/${cycleId}/dag`);
}

export type TaskPlanSummary = {
  id: string;
  status: string;
  validation_report: unknown;
  task_count: number;
};

export function fetchTaskPlans(cycleId: string) {
  return apiRequest<TaskPlanSummary[]>(`/delivery-cycles/${cycleId}/task-plans`);
}

export function fetchTaskPlan(planId: string) {
  return apiRequest<{
    id: string;
    status: string;
    body: Record<string, unknown>;
    validation_report: unknown;
  }>(`/task-plans/${planId}`);
}

export function fetchExecutions(taskId: string) {
  return apiRequest<Execution[]>(`/tasks/${taskId}/executions`);
}

export function fetchIntegrationCandidates(cycleId: string) {
  return apiRequest<IntegrationCandidate[]>(
    `/delivery-cycles/${cycleId}/integration-candidates`,
  );
}

export function fetchObligations(icId: string) {
  return apiRequest<VerificationObligation[]>(`/integration-candidates/${icId}/obligations`);
}

export function fetchDomainEvents(cycleId: string, afterSequence = 0) {
  return apiRequest<DomainEventPayload[]>(
    `/delivery-cycles/${cycleId}/events?after_sequence=${afterSequence}&limit=50`,
  );
}

export function fetchProjectCoverage(projectId: string) {
  return apiRequest<Record<string, unknown>>(`/views/projects/${projectId}/coverage`);
}

export function fetchProjectRepository(projectId: string) {
  return apiRequest<Record<string, unknown>>(`/views/projects/${projectId}/repository`);
}

export function fetchTaskContract(taskId: string) {
  return apiRequest<{
    id: string;
    task_id: string;
    key: string;
    version: number;
    status: string;
    body: Record<string, unknown>;
    content_hash: string | null;
  } | null>(`/tasks/${taskId}/contract`);
}

export function fetchTaskEligibility(taskId: string) {
  return apiRequest<{ eligible: boolean; reasons: string[] }>(`/tasks/${taskId}/eligibility`);
}

export function fetchExecution(executionId: string) {
  return apiRequest<Execution>(`/executions/${executionId}`);
}

export function fetchExecutionEvents(executionId: string) {
  return apiRequest<
    { id: string; event_type: string; payload: Record<string, unknown>; occurred_at: string }[]
  >(`/executions/${executionId}/events`);
}

export function fetchAgentActivity(projectId: string) {
  return apiRequest<Record<string, unknown>>(`/views/projects/${projectId}/agent-activity`);
}

export function fetchIcAssurance(icId: string) {
  return apiRequest<Record<string, unknown>>(`/views/ic/${icId}/assurance`);
}

export function fetchLatestImpactAssessment(cycleId: string) {
  return apiRequest<Record<string, unknown>>(`/delivery-cycles/${cycleId}/impact-assessments/latest`);
}

export function fetchReleaseEligibility(cycleId: string) {
  return apiRequest<{
    id: string;
    delivery_cycle_id: string;
    eligible: boolean;
    conditions: { name: string; ok: boolean; reasons: string[]; inputs_hash: string }[];
    integration_candidate_id: string | null;
  }>(`/delivery-cycles/${cycleId}/release-eligibility`);
}

export function fetchCycleOutcome(cycleId: string) {
  return apiRequest<{ delivery_cycle_id: string; result: string; content: Record<string, unknown> }>(
    `/delivery-cycles/${cycleId}/outcome`,
  );
}

export function fetchProjectReleases(projectId: string) {
  return apiRequest<
    {
      id: string;
      key: string;
      status: string;
      integrated_sha: string;
      delivery_cycle_id: string;
    }[]
  >(`/projects/${projectId}/releases`);
}

export function fetchProjectFeatures(projectId: string) {
  return apiRequest<
    { id: string; key: string; name: string; capability_id: string; status?: string }[]
  >(`/projects/${projectId}/features`);
}

export function fetchCycleKnowledge(cycleId: string) {
  return apiRequest<
    { id: string; class: string; statement: string; source_ref?: string | null }[]
  >(`/delivery-cycles/${cycleId}/knowledge`);
}

export function fetchFeatureLineage(featureId: string) {
  return apiRequest<{ nodes: Record<string, unknown>[]; edges: Record<string, unknown>[] }>(
    `/features/${featureId}/lineage`,
  );
}

export function fetchConnectors() {
  return apiRequest<{ name: string; ok: boolean; message: string }[]>("/connectors");
}

export function fetchCodeIndexVersions(repositoryId: string) {
  return apiRequest<
    { id: string; commit_sha: string; status: string; created_at: string }[]
  >(`/repositories/${repositoryId}/code-index/versions`);
}

export function fetchCodeEntities(indexVersionId: string, qText = "") {
  const q = new URLSearchParams({ index_version_id: indexVersionId });
  if (qText) q.set("q", qText);
  return apiRequest<
    { id: string; stable_key: string; qualified_name: string; file_path: string; type: string }[]
  >(`/code/entities?${q}`);
}

export function fetchAuditVerify(projectId?: string) {
  const q = projectId ? `?project_id=${projectId}` : "";
  return apiRequest<{
    valid: boolean;
    project_id: string | null;
    rows_checked: number;
    first_invalid_seq: number | null;
    message: string;
  }>(`/audit/verify${q}`);
}

export function fetchApproval(approvalId: string) {
  return apiRequest<{
    id: string;
    key: string;
    approval_type: string;
    subject_type: string;
    subject_id: string;
    subject_version: number;
    subject_hash: string;
    status: string;
    project_id: string;
    delivery_cycle_id: string | null;
  }>(`/approvals/${approvalId}`);
}

export function fetchClarification(clarificationId: string) {
  return apiRequest<{
    id: string;
    key: string;
    question: string;
    status: string;
    answer: string | null;
  }>(`/clarifications/${clarificationId}`);
}

export function answerClarification(clarificationId: string, answer: string) {
  return apiRequest<Record<string, unknown>>(`/clarifications/${clarificationId}/answer`, {
    method: "POST",
    body: { answer },
  });
}

export function createDeliveryCycle(
  projectId: string,
  body: { type: string; objective: string; repository_id?: string | null },
  idempotencyKey?: string,
) {
  return apiRequest<DeliveryCycle>(`/projects/${projectId}/delivery-cycles`, {
    method: "POST",
    body,
    idempotencyKey,
  });
}

export function createOrchestratorSession(body: {
  project_id?: string | null;
  delivery_cycle_id?: string | null;
}) {
  return apiRequest<{
    id: string;
    project_id: string | null;
    delivery_cycle_id: string | null;
    turns: { role: string; text: string; execution_id?: string }[];
    expires_at: string;
  }>("/orchestrator/sessions", { method: "POST", body });
}

export function postOrchestratorTurn(sessionId: string, message: string) {
  return apiRequest<{ execution_id: string }>(`/orchestrator/sessions/${sessionId}/turns`, {
    method: "POST",
    body: { message },
  });
}

export function fetchOrchestratorSession(sessionId: string) {
  return apiRequest<{
    id: string;
    turns: { role: string; text: string; execution_id?: string; message?: string }[];
  }>(`/orchestrator/sessions/${sessionId}`);
}

export function fetchAuditForTarget(targetType: string, targetId: string) {
  const q = new URLSearchParams({ target_type: targetType, target_id: targetId });
  return apiRequest<
    {
      id: string;
      action: string;
      actor_id: string;
      before: unknown;
      after: unknown;
      occurred_at: string;
    }[]
  >(`/audit?${q}`);
}
