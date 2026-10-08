import { apiRequest } from "@/src/api/client";
export {
  answerClarification,
  createDeliveryCycle,
  createOrchestratorSession,
  postOrchestratorTurn,
} from "@/src/api/commands";
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
import type { OrchestratorSession } from "@/src/api/types/orchestrator";
import type { MaterializationAttempt, Repository } from "@/src/api/types/repository";
import type {
  BrownfieldDiscovery,
  ChangeInterpretation,
  ChangeRequestSummary,
  CycleSpecDelta,
  DefectDetail,
  DefectSummary,
  ObservedBehavior,
  ReadinessAssessment,
  CycleFinding,
  ReviewQueueItem,
} from "@/src/api/types/journey";
import type {
  ArchitectureView,
  Capability,
  Clarification,
  Feature,
  FeatureSpecDetail,
  FeatureSpecSummary,
  ImplementationSpecSummary,
  ProductDecompositionSummary,
  ProductSourceContent,
  ProductSourceSummary,
} from "@/src/api/types/product-model";

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

export function getNextTransitions(cycleId: string) {
  return apiRequest<TransitionPreview[]>(`/delivery-cycles/${cycleId}/next-transitions`);
}

/** @deprecated Use `getNextTransitions` */
export const fetchNextTransitions = getNextTransitions;

export function fetchCycleOverview(cycleId: string) {
  return apiRequest<CycleOverviewView>(`/views/delivery-cycles/${cycleId}/overview`);
}

export function fetchControlPlaneSummary(cycleId: string) {
  return apiRequest<ControlPlaneSummaryView>(`/views/delivery-cycles/${cycleId}/control-plane`);
}

export function fetchProjectOverview(projectId: string) {
  return apiRequest<Record<string, unknown>>(`/views/projects/${projectId}/overview`);
}

export function fetchInbox(params?: { projectId?: string; cycleId?: string }) {
  const search = new URLSearchParams();
  if (params?.projectId) search.set("project_id", params.projectId);
  if (params?.cycleId) search.set("delivery_cycle_id", params.cycleId);
  const qs = search.toString();
  return apiRequest<InboxItem[]>(`/views/inbox${qs ? `?${qs}` : ""}`);
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

export function listTaskPlans(cycleId: string) {
  return fetchTaskPlans(cycleId);
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

export function listProjectRepositories(projectId: string) {
  return apiRequest<Repository[]>(`/projects/${projectId}/repositories`);
}

export function getRepository(repositoryId: string) {
  return apiRequest<Repository>(`/repositories/${repositoryId}`);
}

export function listMaterializations(repositoryId: string) {
  return apiRequest<MaterializationAttempt[]>(`/repositories/${repositoryId}/materializations`);
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

export function fetchCycleKnowledge(cycleId: string) {
  return apiRequest<
    { id: string; class: string; statement: string; source_ref?: string | null }[]
  >(`/delivery-cycles/${cycleId}/knowledge`);
}

export function listChangeRequests(projectId: string) {
  return apiRequest<ChangeRequestSummary[]>(`/projects/${projectId}/change-requests`);
}

export function getChangeInterpretation(cycleId: string) {
  return apiRequest<ChangeInterpretation>(`/delivery-cycles/${cycleId}/change-interpretation`);
}

export function getCycleSpecDelta(cycleId: string) {
  return apiRequest<CycleSpecDelta>(`/delivery-cycles/${cycleId}/spec-delta`);
}

export function listDefects(projectId: string) {
  return apiRequest<DefectSummary[]>(`/projects/${projectId}/defects`);
}

export function getDefect(defectId: string) {
  return apiRequest<DefectDetail>(`/defects/${defectId}`);
}

export function listDefectReproductions(defectId: string) {
  return apiRequest<Record<string, unknown>[]>(`/defects/${defectId}/reproductions`);
}

export function getDefectRootCause(defectId: string) {
  return apiRequest<Record<string, unknown>>(`/defects/${defectId}/root-cause`);
}

export function getBrownfieldDiscovery(cycleId: string) {
  return apiRequest<BrownfieldDiscovery>(`/delivery-cycles/${cycleId}/discovery`);
}

export function listObservedBehaviors(cycleId: string, kind?: string) {
  const q = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return apiRequest<ObservedBehavior[]>(`/delivery-cycles/${cycleId}/observed-behaviors${q}`);
}

export function getRecoveryProposals(cycleId: string) {
  return apiRequest<{ proposals: Record<string, unknown>[] }>(
    `/delivery-cycles/${cycleId}/recovery`,
  );
}

export function getReviewQueue(cycleId: string) {
  return apiRequest<ReviewQueueItem[]>(`/delivery-cycles/${cycleId}/review-queue`);
}

export function listFindings(cycleId: string) {
  return apiRequest<CycleFinding[]>(`/delivery-cycles/${cycleId}/findings`);
}

export function getReadinessAssessment(cycleId: string, recompute = false) {
  const q = recompute ? "?recompute=true" : "";
  return apiRequest<ReadinessAssessment | null>(`/delivery-cycles/${cycleId}/readiness${q}`);
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

export function listSources(projectId: string) {
  return apiRequest<ProductSourceSummary[]>(`/projects/${projectId}/sources`);
}

export function getSourceContent(projectId: string, sourceId: string) {
  return apiRequest<ProductSourceContent>(`/projects/${projectId}/sources/${sourceId}/content`);
}

export function listCapabilities(projectId: string) {
  return apiRequest<Capability[]>(`/projects/${projectId}/capabilities`);
}

export function listFeatures(projectId: string) {
  return apiRequest<Feature[]>(`/projects/${projectId}/features`);
}

/** Alias for existing dashboard usage. */
export const fetchProjectFeatures = listFeatures;

export function listFeatureSpecs(featureId: string) {
  return apiRequest<FeatureSpecSummary[]>(`/features/${featureId}/specs`);
}

export function getFeatureSpec(specId: string) {
  return apiRequest<FeatureSpecDetail>(`/specs/${specId}`);
}

export function listDecompositions(cycleId: string) {
  return apiRequest<ProductDecompositionSummary[]>(
    `/delivery-cycles/${cycleId}/decompositions`,
  );
}

export function listClarifications(status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiRequest<Clarification[]>(`/clarifications${q}`);
}

export function getProjectArchitecture(projectId: string) {
  return apiRequest<ArchitectureView>(`/projects/${projectId}/architecture`);
}

export function listImplementationSpecs(featureSpecId: string) {
  return apiRequest<ImplementationSpecSummary[]>(
    `/features/${featureSpecId}/implementation-specs`,
  );
}

export function getTaskDag(cycleId: string) {
  return fetchTaskDag(cycleId);
}

export function getApproval(approvalId: string) {
  return fetchApproval(approvalId);
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

export function listApprovals(params?: { status?: string }) {
  const q = params?.status ? `?status=${encodeURIComponent(params.status)}` : "";
  return apiRequest<
    {
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
    }[]
  >(`/approvals${q}`);
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

export function fetchOrchestratorSession(sessionId: string) {
  return apiRequest<OrchestratorSession>(`/orchestrator/sessions/${sessionId}`);
}

export function getRelease(releaseId: string) {
  return apiRequest<{
    id: string;
    key: string;
    project_id: string;
    delivery_cycle_id: string;
    integrated_sha: string;
    status: string;
    manifest_id: string | null;
    tag: string | null;
  }>(`/releases/${releaseId}`);
}

export function getReleaseManifest(releaseId: string) {
  return apiRequest<{ content: Record<string, unknown>; content_hash: string }>(
    `/releases/${releaseId}/manifest`,
  );
}

/** Alias */
export function getReleaseEligibility(cycleId: string) {
  return fetchReleaseEligibility(cycleId);
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
