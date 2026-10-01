import { openEnum, strictEnum } from "./open-enum";

export const DeliveryCycleType = strictEnum([
  "GREENFIELD_BUILD",
  "BROWNFIELD_ONBOARDING",
  "FEATURE_CHANGE",
  "BUG_FIX",
  "REMEDIATION",
] as const);

export const ProjectReadiness = strictEnum([
  "UNKNOWN",
  "ONBOARDING",
  "READY_FOR_CHANGE",
] as const);

export const TaskStatus = strictEnum([
  "DRAFT",
  "BLOCKED",
  "READY",
  "QUEUED",
  "RUNNING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
  "STALE",
  "REVALIDATION_REQUIRED",
] as const);

export const ExecutionStatus = strictEnum([
  "QUEUED",
  "LEASED",
  "STARTED",
  "CHECKPOINTED",
  "OUTPUT_PRODUCED",
  "VALIDATING",
  "COMMITTED",
  "COMPLETED",
  "FAILED",
  "TIMED_OUT",
  "CANCELLED",
  "STALE",
] as const);

export const ActionStatus = openEnum(
  [
    "REQUESTED",
    "DENIED",
    "PENDING_APPROVAL",
    "APPROVED",
    "EXECUTING",
    "SUCCEEDED",
    "FAILED",
    "RECONCILIATION_REQUIRED",
  ] as const,
  "ActionStatus",
);

export const ICStatus = strictEnum([
  "CREATED",
  "INTEGRATING",
  "VALIDATING",
  "READY",
  "CONFLICT",
  "FAILED",
  "SUPERSEDED",
] as const);

export const GateStatus = strictEnum([
  "PENDING",
  "PASS",
  "FAIL",
  "SUPERSEDED",
] as const);

export const KnowledgeClass = strictEnum([
  "FACT",
  "INFERENCE",
  "UNCERTAINTY",
  "DECISION",
  "ASSUMPTION",
] as const);

export const SpecCodeLinkOrigin = strictEnum([
  "GENERATED_LINEAGE",
  "DISCOVERED",
  "HUMAN_CONFIRMED",
] as const);

export const ImpactKind = strictEnum([
  "DIRECT",
  "TRANSITIVE",
  "CANDIDATE",
  "SEMANTIC_CANDIDATE",
] as const);

export const RetrievalSource = strictEnum([
  "STRUCTURAL",
  "LEXICAL",
  "SEMANTIC",
] as const);

export const IndexKind = strictEnum(["CANDIDATE", "CANONICAL"] as const);

export const ApprovalStatus = strictEnum([
  "PENDING",
  "APPROVED",
  "REJECTED",
  "CHANGES_REQUESTED",
  "EXPIRED",
  "CANCELLED",
] as const);

export const ApprovalType = openEnum(
  [
    "SCOPE",
    "ARCHITECTURE",
    "ARCHITECTURE_DELTA",
    "IMPLEMENTATION_SPEC",
    "SPEC_DELTA",
    "SPEC_DECISION",
    "REPAIR_SPEC",
    "PROMOTION",
    "FINDING_WAIVER",
    "ACTION",
    "RELEASE",
    "READINESS",
    "UNREPRODUCED_REPAIR",
    "EXPECTED_BEHAVIOR",
    "DEPLOYMENT",
  ] as const,
  "ApprovalType",
);

export const ReleaseStatus = strictEnum([
  "DRAFT",
  "ELIGIBLE",
  "NOT_ELIGIBLE",
  "APPROVED",
  "EXECUTING",
  "RELEASED",
  "FAILED",
  "SUPERSEDED",
] as const);

export const ActorRole = strictEnum([
  "OPERATOR",
  "APPROVER",
  "VIEWER",
  "SYSTEM",
  "INTEGRATION",
] as const);

export const WorkType = strictEnum([
  "ANALYSIS",
  "CODE_CHANGE",
  "VERIFICATION",
  "INTEGRATION",
  "RELEASE",
] as const);
