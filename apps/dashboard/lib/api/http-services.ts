import { CapabilityPendingError } from "./errors";
import type { OlympusServices } from "./olympus-services";

/** Live HTTP adapters — pending until control-api is available. */
export function createHttpServices(): OlympusServices {
  const pending = (cap: string, phase: string) => () => {
    throw new CapabilityPendingError(cap, phase);
  };
  const pendingAsync = (cap: string, phase: string) => async () => {
    throw new CapabilityPendingError(cap, phase);
  };

  return {
    auth: { me: pendingAsync("auth/me", "01"), setViewerMode: () => {} },
    repositories: {
      forProject: pendingAsync("repositories", "01"),
      get: pendingAsync("repositories/{id}", "01"),
      workspace: pendingAsync("repository-workspace", "01"),
      revisions: pendingAsync("repository-revisions", "01"),
      materializations: pendingAsync("repository-materializations", "04"),
      executionWorkspaces: pendingAsync("execution-workspaces", "04"),
      commitLedger: pendingAsync("repository-commits", "01"),
    },
    artifacts: {
      get: pendingAsync("artifacts", "03"),
      textContent: pendingAsync("artifacts/content", "03"),
    },
    projects: {
      list: pendingAsync("projects", "01"),
      get: pendingAsync("projects", "01"),
      summary: pendingAsync("projects/summary", "17"),
    },
    deliveryCycles: {
      list: pendingAsync("delivery-cycles", "01"),
      get: pendingAsync("delivery-cycles", "01"),
      nextTransitions: pendingAsync("next-transitions", "17"),
      events: pendingAsync("events", "01"),
      command: pendingAsync("commands", "01"),
    },
    tasks: {
      listByCycle: pendingAsync("tasks", "01"),
      get: pendingAsync("tasks", "01"),
      dag: pendingAsync("task-dag", "06"),
      contract: pendingAsync("contract", "01"),
      eligibility: pendingAsync("eligibility", "03"),
    },
    executions: {
      listByTask: pendingAsync("executions", "03"),
      get: pendingAsync("executions", "03"),
      listByCycle: pendingAsync("executions", "03"),
      snapshot: pendingAsync("execution-snapshot", "03"),
      worktree: pendingAsync("execution-worktree", "04"),
      workspace: pendingAsync("execution-workspace", "04"),
      lease: pendingAsync("execution-lease", "03"),
      runtimeMetadata: pendingAsync("runtime-metadata", "02"),
      modelCalls: pendingAsync("model-calls", "02"),
      artifacts: pendingAsync("execution-artifacts", "03"),
      candidateCommit: pendingAsync("candidate-commit", "04"),
      actions: pendingAsync("execution-actions", "04"),
    },
    approvals: {
      pending: pendingAsync("approvals", "01"),
      decide: pendingAsync("approvals", "01"),
    },
    release: {
      eligibility: pendingAsync("release-eligibility", "10"),
      get: pendingAsync("releases", "10"),
      list: pendingAsync("releases", "10"),
      forCycle: pendingAsync("releases/for-cycle", "10"),
      manifest: pendingAsync("release-manifest", "10"),
    },
    assurance: {
      gatesForIc: pendingAsync("gates", "09"),
      findings: pendingAsync("findings", "09"),
      evidence: pendingAsync("evidence", "09"),
      obligations: pendingAsync("obligations", "09"),
      coverage: pendingAsync("coverage", "09"),
      reviews: pendingAsync("reviews", "09"),
    },
    integration: {
      listByCycle: pendingAsync("integration-candidates", "08"),
      get: pendingAsync("integration-candidates", "08"),
      commits: pendingAsync("integration-candidate-commits", "08"),
    },
    inbox: { list: pendingAsync("inbox", "17") },
    views: {
      projectOverview: pendingAsync("views/project-overview", "17"),
      cycleOverview: pendingAsync("views/cycle-overview", "17"),
      controlPlane: pendingAsync("views/control-plane", "17"),
    },
    controlPlane: {
      forCycle: pendingAsync("control-plane", "17"),
      explain: pendingAsync("control-plane/explain", "17"),
    },
    code: {
      canonicalIndex: pendingAsync("code-index/canonical", "07"),
      listVersions: pendingAsync("code-index/versions", "07"),
      getEntity: pendingAsync("code/entities", "07"),
      entities: pendingAsync("code/entities/list", "07"),
      byStableKey: pendingAsync("code/entities/by-stable-key", "07"),
      neighbors: pendingAsync("code/entities/neighbors", "07"),
      search: pendingAsync("code/search", "07"),
      relations: pendingAsync("code/relations", "07"),
      entityChanges: pendingAsync("code-entity-changes", "08"),
      versionDiff: pendingAsync("code-index/diff", "07"),
    },
    lineage: {
      query: pendingAsync("lineage", "08"),
      specCodeLinks: pendingAsync("spec-code-links", "08"),
    },
    impact: {
      forCycle: pendingAsync("impact-assessments", "13"),
      get: pendingAsync("impact-assessments", "13"),
    },
    brownfield: {
      discovery: pendingAsync("brownfield/discovery", "11"),
      discoverySteps: pendingAsync("brownfield/discovery-steps", "11"),
      observedBehaviors: pendingAsync("observed-behaviors", "11"),
      recoveredSpecs: pendingAsync("brownfield/recovered", "11"),
      promotions: pendingAsync("promotions", "12"),
      baselines: pendingAsync("baselines", "12"),
      baselineSet: pendingAsync("baseline-set", "12"),
      readiness: pendingAsync("readiness", "12"),
    },
    actions: {
      list: pendingAsync("actions", "04"),
      get: pendingAsync("actions", "04"),
      result: pendingAsync("action-results", "04"),
    },
    defects: {
      get: pendingAsync("defects", "15"),
      forCycle: pendingAsync("defects", "15"),
      reproductions: pendingAsync("reproductions", "15"),
      trace: pendingAsync("trace-correlation", "15"),
      rca: pendingAsync("root-cause", "15"),
    },
    changeRequests: {
      list: pendingAsync("change-requests", "14"),
      get: pendingAsync("change-requests", "14"),
    },
    connectors: {
      list: pendingAsync("connectors", "16"),
      inboundEvents: pendingAsync("inbound-events", "16"),
      actions: pendingAsync("connector-actions", "16"),
    },
    product: {
      sources: pendingAsync("product/sources", "05"),
      capabilities: pendingAsync("product/capabilities", "05"),
      features: pendingAsync("product/features", "05"),
      featureSpecs: pendingAsync("product/feature-specs", "05"),
      acceptanceCriteria: pendingAsync("product/acceptance-criteria", "05"),
      requirements: pendingAsync("product/requirements", "05"),
      userStories: pendingAsync("product/user-stories", "05"),
      knowledge: pendingAsync("knowledge", "05"),
      specDeltas: pendingAsync("spec-deltas", "13"),
    },
    planning: {
      implementationSpecs: pendingAsync("implementation-specs", "06"),
      architecture: pendingAsync("architecture", "06"),
      taskPlans: pendingAsync("task-plans", "06"),
    },
    events: {
      forProject: pendingAsync("project-events", "01"),
    },
  };
}
