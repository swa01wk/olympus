import { z } from "zod";
import { IsoDateTime, Uuid, VersionedRef } from "./common";
import {
  ApprovalStatus,
  ApprovalType,
  DeliveryCycleType,
  ExecutionStatus,
  GateStatus,
  ICStatus,
  ProjectReadiness,
  ReleaseStatus,
  TaskStatus,
  WorkType,
} from "./enums";

export { DomainEvent } from "./events";
export {
  CodeIndexVersion,
  CodeEntity,
  CodeRelation,
  EntityType,
  IndexPointer,
  CodeEntityChange,
  RetrievalHit,
} from "./code-intelligence";
export {
  SpecCodeLink,
  LineageGraph,
  LineageNode,
  LineageEdge,
} from "./traceability";
export {
  ActionRequest,
  ActionResult,
  PolicyDecision,
  Worktree,
  ExecutionWorkspace,
  CandidateCommit,
} from "./actions";
export {
  Repository,
  RepositoryWorkspace,
  RepositoryRevision,
  RepositoryMaterialization,
  CommitLedgerEntry,
} from "./repository";
export { ExecutionLease, ModelCall, Artifact, RuntimeMetadata } from "./runtime";
export { IntegrationCandidateCommit } from "./integration-ext";
export {
  Evidence,
  VerificationObligation,
  AcceptanceCoverage,
  Review,
} from "./assurance-ext";
export { ReleaseManifest, ReleaseManifestContent } from "./release-ext";
export { ControlDecision, ControlConditionResult } from "./control-plane-ext";
export {
  ProductSource,
  Capability,
  Feature,
  FeatureSpec,
  AcceptanceCriterion,
  Requirement,
  UserStory,
  KnowledgeItem,
} from "./product";
export { Architecture, ImplementationSpec, TaskPlan } from "./planning";
export {
  RecoveredSpec,
  BehavioralBaseline,
  BaselineSet,
  ReadinessAssessment,
  RepositoryDiscovery,
  ObservedBehavior,
  PromotionDecision,
  DiscoveryStep,
} from "./brownfield";
export { ImpactAssessment, ImpactItem, SpecDelta } from "./impact";
export { Defect, Reproduction, TraceCorrelation, RootCauseAnalysis } from "./defect";
export {
  ConnectorConfig,
  InboundEvent,
  ConnectorAction,
  ChangeRequest,
} from "./connectors";
export { ProjectSummaryView, CycleOverviewView, ControlPlaneView } from "./views";

export const Project = z.object({
  id: Uuid,
  key: z.string(),
  name: z.string(),
  description: z.string().nullable().optional(),
  readiness_state: ProjectReadiness,
  active_baseline_set_id: Uuid.nullable().optional(),
});

export const DeliveryCycle = z.object({
  id: Uuid,
  project_id: Uuid,
  key: z.string(),
  type: DeliveryCycleType,
  objective: z.string(),
  state: z.string(),
  state_version: z.number().int(),
  repository_id: Uuid.nullable().optional(),
  base_sha: z.string().nullable().optional(),
  allowed_commands: z
    .array(
      z.object({
        command: z.string(),
        allowed: z.boolean(),
        guard_results: z
          .array(z.object({ guard: z.string(), ok: z.boolean(), reason: z.string().optional() }))
          .optional(),
      }),
    )
    .optional(),
});

export const GuardResult = z.object({
  guard: z.string(),
  ok: z.boolean(),
  reason: z.string().optional(),
});

export const TransitionPreview = z.object({
  command: z.string(),
  target_state: z.string(),
  allowed: z.boolean(),
  guard_results: z.array(GuardResult),
});

export const Task = z.object({
  id: Uuid,
  delivery_cycle_id: Uuid,
  key: z.string(),
  title: z.string(),
  work_type: WorkType,
  origin: z.string(),
  status: TaskStatus,
  priority: z.number().int(),
  blocked_reason: z.string().nullable().optional(),
  current_contract_id: Uuid.nullable().optional(),
});

export const TaskDependency = z.object({
  task_id: Uuid,
  depends_on_task_id: Uuid,
  kind: z.string(),
});

export const TaskContractBody = z.object({
  objective: z.string(),
  work_type: WorkType,
  inputs: z.array(VersionedRef),
  allowed_scope: z.array(z.string()),
  allowed_actions: z.array(z.string()),
  required_outputs: z.array(z.string()),
  agent_profile: z.string().nullable().optional(),
  executor_kind: z.enum(["AGENT_RUNTIME", "DETERMINISTIC"]),
  model_alias: z.string().nullable().optional(),
});

export const TaskContract = z.object({
  id: Uuid,
  task_id: Uuid,
  key: z.string(),
  version: z.number().int(),
  status: z.enum(["DRAFT", "ISSUED", "SUPERSEDED"]),
  body: TaskContractBody,
  content_hash: z.string().nullable().optional(),
  compiled_by: z.string(),
});

export const Execution = z.object({
  id: Uuid,
  key: z.string(),
  task_id: Uuid,
  delivery_cycle_id: Uuid,
  attempt_number: z.number().int(),
  status: ExecutionStatus,
  executor_kind: z.string(),
  agent_profile: z.string().nullable().optional(),
  snapshot_id: Uuid.nullable().optional(),
  previous_execution_id: Uuid.nullable().optional(),
  failure_class: z.string().nullable().optional(),
  started_at: IsoDateTime.nullable().optional(),
  finished_at: IsoDateTime.nullable().optional(),
});

export const ExecutionSnapshot = z.object({
  id: Uuid,
  execution_id: Uuid,
  task_contract_hash: z.string(),
  base_commit: z.string().nullable().optional(),
  snapshot_hash: z.string(),
  content: z.record(z.string(), z.unknown()),
});

export const Approval = z.object({
  id: Uuid,
  key: z.string(),
  project_id: Uuid,
  delivery_cycle_id: Uuid.nullable().optional(),
  approval_type: ApprovalType,
  subject_type: z.string(),
  subject_id: Uuid,
  subject_version: z.number().int().nullable().optional(),
  subject_hash: z.string().nullable().optional(),
  status: ApprovalStatus,
});

export const IntegrationCandidate = z.object({
  id: Uuid,
  key: z.string(),
  delivery_cycle_id: Uuid,
  repository_id: Uuid,
  base_sha: z.string(),
  integration_branch: z.string().nullable().optional(),
  integrated_sha: z.string().nullable().optional(),
  status: ICStatus,
  ordering: z.array(
    z.object({
      task_key: z.string(),
      candidate_commit_sha: z.string(),
      position: z.number().int(),
      reason: z.string().optional(),
    }),
  ),
  integration_execution_id: Uuid.nullable().optional(),
  checks_artifact_id: Uuid.nullable().optional(),
  canonical_index_version_id: Uuid.nullable().optional(),
  canonical_revision_id: Uuid.nullable().optional(),
  supersedes_id: Uuid.nullable().optional(),
});

export const Gate = z.object({
  id: Uuid,
  key: z.string(),
  delivery_cycle_id: Uuid,
  integration_candidate_id: Uuid,
  gate_type: z.string(),
  status: GateStatus,
  recommendation: z.record(z.string(), z.unknown()).nullable().optional(),
  reasons: z.array(z.string()).optional(),
  inputs_hash: z.string().nullable().optional(),
  policy_version_id: Uuid.nullable().optional(),
  finalized_by: z.string().nullable().optional(),
  finalized_at: IsoDateTime.nullable().optional(),
});

export const Finding = z.object({
  id: Uuid,
  key: z.string(),
  project_id: Uuid.optional(),
  delivery_cycle_id: Uuid,
  integration_candidate_id: Uuid.nullable().optional(),
  commit_sha: z.string().nullable().optional(),
  source: z.string(),
  category: z.string(),
  severity: z.string(),
  blocking: z.boolean(),
  title: z.string(),
  detail: z.record(z.string(), z.unknown()).optional(),
  code_refs: z.array(z.unknown()).optional(),
  spec_refs: z.array(z.unknown()).optional(),
  remediation_task_id: Uuid.nullable().optional(),
  resolved_by_ic_id: Uuid.nullable().optional(),
  status: z.string(),
});

export const ReleaseEligibilityEvaluation = z.object({
  delivery_cycle_id: Uuid,
  integration_candidate_id: Uuid,
  eligible: z.boolean(),
  conditions: z.array(
    z.object({
      name: z.string(),
      ok: z.boolean(),
      reasons: z.array(z.string()),
      inputs_hash: z.string().optional(),
      subject_refs: z
        .array(
          z.object({
            type: z.string(),
            id: Uuid.optional(),
            key: z.string().optional(),
          }),
        )
        .optional(),
    }),
  ),
});

export const Release = z.object({
  id: Uuid,
  key: z.string(),
  project_id: Uuid,
  delivery_cycle_id: Uuid,
  integration_candidate_id: Uuid,
  integrated_sha: z.string(),
  status: ReleaseStatus,
});

export const ActorMe = z.object({
  actor_id: Uuid,
  kind: z.enum(["HUMAN", "AGENT", "SYSTEM", "INTEGRATION"]),
  name: z.string(),
  roles: z.array(z.string()),
  scopes: z.array(z.string()).optional(),
});
