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
  inbox: ["views", "inbox"] as const,
  projectOverview: (projectId: string) => ["views", "project-overview", projectId] as const,
  coverage: (projectId: string) => ["views", "coverage", projectId] as const,
  repository: (projectId: string) => ["views", "repository", projectId] as const,
  agentActivity: (projectId: string) => ["views", "agent-activity", projectId] as const,
  features: (projectId: string) => ["product", "features", projectId] as const,
  knowledge: (cycleId: string) => ["knowledge", cycleId] as const,
  taskContract: (taskId: string) => ["task-contract", taskId] as const,
  taskEligibility: (taskId: string) => ["task-eligibility", taskId] as const,
  execution: (executionId: string) => ["executions", "detail", executionId] as const,
  executionEvents: (executionId: string) => ["executions", "events", executionId] as const,
  icAssurance: (icId: string) => ["views", "ic-assurance", icId] as const,
  impactLatest: (cycleId: string) => ["impact", "latest", cycleId] as const,
  releaseEligibility: (cycleId: string) => ["release", "eligibility", cycleId] as const,
  outcome: (cycleId: string) => ["outcome", cycleId] as const,
  releases: (projectId: string) => ["releases", projectId] as const,
  lineage: (featureId: string) => ["lineage", "feature", featureId] as const,
  connectors: ["connectors"] as const,
  codeEntities: (repositoryId: string, prefix: string) =>
    ["code-entities", repositoryId, prefix] as const,
  auditVerify: (projectId: string) => ["audit", "verify", projectId] as const,
  auditTarget: (targetType: string, targetId: string) =>
    ["audit", "target", targetType, targetId] as const,
};
