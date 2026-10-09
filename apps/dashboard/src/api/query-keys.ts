export const queryKeys = {
  actor: ["actor", "me"] as const,
  projects: {
    all: ["projects"] as const,
    detail: (projectId: string) => ["projects", projectId] as const,
  },
  cycles: {
    list: (projectId: string) => ["delivery-cycles", projectId] as const,
    detail: (cycleId: string) => ["delivery-cycles", "detail", cycleId] as const,
    overview: (cycleId: string) => ["views", "cycle-overview", cycleId] as const,
    controlPlane: (cycleId: string) => ["views", "control-plane", cycleId] as const,
    transitions: (cycleId: string) => ["delivery-cycles", "transitions", cycleId] as const,
  },
  tasks: {
    byCycle: (cycleId: string) => ["tasks", "cycle", cycleId] as const,
    detail: (taskId: string) => ["tasks", "detail", taskId] as const,
    dag: (cycleId: string) => ["views", "task-dag", cycleId] as const,
  },
  taskPlans: {
    list: (cycleId: string) => ["task-plans", "cycle", cycleId] as const,
    detail: (planId: string) => ["task-plans", "detail", planId] as const,
  },
  executions: {
    byTask: (taskId: string) => ["executions", "task", taskId] as const,
  },
  integration: {
    candidates: (cycleId: string) => ["integration-candidates", cycleId] as const,
    obligations: (icId: string) => ["obligations", icId] as const,
  },
  inbox: (params?: { projectId?: string; cycleId?: string }) =>
    ["views", "inbox", params?.projectId ?? null, params?.cycleId ?? null] as const,
  inboxRoot: ["views", "inbox"] as const,
  projectOverview: (projectId: string) => ["views", "project-overview", projectId] as const,
  coverage: (projectId: string) => ["views", "coverage", projectId] as const,
  repository: (projectId: string) => ["views", "repository", projectId] as const,
  repositories: {
    list: (projectId: string) => ["repositories", "list", projectId] as const,
    detail: (repositoryId: string) => ["repositories", "detail", repositoryId] as const,
    materializations: (repositoryId: string) =>
      ["repositories", "materializations", repositoryId] as const,
  },
  agentActivity: (projectId: string) => ["views", "agent-activity", projectId] as const,
  features: (projectId: string) => ["product", "features", projectId] as const,
  capabilities: (projectId: string) => ["product", "capabilities", projectId] as const,
  sources: {
    list: (projectId: string) => ["product", "sources", projectId] as const,
    content: (projectId: string, sourceId: string) =>
      ["product", "sources", projectId, sourceId, "content"] as const,
  },
  featureSpecs: (featureId: string) => ["product", "feature-specs", featureId] as const,
  featureSpecDetail: (specId: string) => ["product", "feature-spec", specId] as const,
  decompositions: (cycleId: string) => ["product", "decompositions", cycleId] as const,
  clarificationsForProject: (projectId: string) => ["clarifications", projectId] as const,
  clarifications: (projectId: string, status?: string | null) =>
    ["clarifications", projectId, status ?? null] as const,
  architecture: (projectId: string) => ["planning", "architecture", projectId] as const,
  architectureDetail: (architectureId: string) =>
    ["planning", "architecture-detail", architectureId] as const,
  implementationSpecs: (featureSpecId: string) =>
    ["planning", "implementation-specs", featureSpecId] as const,
  approvals: {
    detail: (approvalId: string) => ["approvals", approvalId] as const,
    list: (status?: string | null) => ["approvals", "list", status ?? null] as const,
  },
  release: {
    detail: (releaseId: string) => ["releases", "detail", releaseId] as const,
    manifest: (releaseId: string) => ["releases", "manifest", releaseId] as const,
  },
  orchestrator: {
    session: (sessionId: string) => ["orchestrator", "session", sessionId] as const,
  },
  knowledge: (cycleId: string) => ["knowledge", cycleId] as const,
  taskContract: (taskId: string) => ["task-contract", taskId] as const,
  taskEligibility: (taskId: string) => ["task-eligibility", taskId] as const,
  execution: (executionId: string) => ["executions", "detail", executionId] as const,
  executionEvents: (executionId: string) => ["executions", "events", executionId] as const,
  icAssurance: (icId: string) => ["views", "ic-assurance", icId] as const,
  impactLatest: (cycleId: string) => ["impact", "latest", cycleId] as const,
  journey: {
    changeRequests: (projectId: string) => ["journey", "change-requests", projectId] as const,
    changeInterpretation: (cycleId: string) => ["journey", "change-interpretation", cycleId] as const,
    cycleSpecDelta: (cycleId: string) => ["journey", "spec-delta", cycleId] as const,
    defects: (projectId: string) => ["journey", "defects", projectId] as const,
    defect: (defectId: string) => ["journey", "defect", defectId] as const,
    defectReproductions: (defectId: string) => ["journey", "defect-repro", defectId] as const,
    defectRootCause: (defectId: string) => ["journey", "defect-rca", defectId] as const,
    expectedBehaviorReview: (resolutionId: string) =>
      ["journey", "expected-behavior", resolutionId] as const,
    baselines: (projectId: string) => ["journey", "baselines", projectId] as const,
    discovery: (cycleId: string) => ["journey", "discovery", cycleId] as const,
    observedBehaviors: (cycleId: string) => ["journey", "observed", cycleId] as const,
    recovery: (cycleId: string) => ["journey", "recovery", cycleId] as const,
    reviewQueue: (cycleId: string) => ["journey", "review-queue", cycleId] as const,
    readiness: (cycleId: string) => ["journey", "readiness", cycleId] as const,
    findings: (cycleId: string) => ["journey", "findings", cycleId] as const,
  },
  releaseEligibility: (cycleId: string) => ["release", "eligibility", cycleId] as const,
  outcome: (cycleId: string) => ["outcome", cycleId] as const,
  releases: (projectId: string) => ["releases", projectId] as const,
  lineage: (featureId: string) => ["lineage", "feature", featureId] as const,
  connectors: ["connectors"] as const,
  policyCurrent: ["policy", "current"] as const,
  codeEntities: (repositoryId: string, prefix: string) =>
    ["code-entities", repositoryId, prefix] as const,
  auditVerify: (projectId: string) => ["audit", "verify", projectId] as const,
  auditTarget: (targetType: string, targetId: string) =>
    ["audit", "target", targetType, targetId] as const,
};
