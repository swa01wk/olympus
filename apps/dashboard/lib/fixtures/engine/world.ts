import type {
  AcceptanceCoverage,
  AcceptanceCriterion,
  ActionRequest,
  ActionResult,
  Approval,
  Architecture,
  Artifact,
  BaselineSet,
  BehavioralBaseline,
  CandidateCommit,
  Capability,
  ChangeRequest,
  CodeEntity,
  CodeEntityChange,
  CodeIndexVersion,
  CodeRelation,
  CommitLedgerEntry,
  ConnectorAction,
  ConnectorConfig,
  ControlDecision,
  Defect,
  DeliveryCycle,
  DomainEvent,
  Evidence,
  Execution,
  ExecutionLease,
  ExecutionSnapshot,
  ExecutionWorkspace,
  Feature,
  FeatureSpec,
  Finding,
  Gate,
  ImpactAssessment,
  ImplementationSpec,
  InboundEvent,
  IndexPointer,
  IntegrationCandidate,
  IntegrationCandidateCommit,
  KnowledgeItem,
  LineageGraph,
  ModelCall,
  ObservedBehavior,
  ProductSource,
  Project,
  PromotionDecision,
  ReadinessAssessment,
  RecoveredSpec,
  Release,
  ReleaseEligibilityEvaluation,
  ReleaseManifest,
  Repository,
  RepositoryMaterialization,
  RepositoryRevision,
  RepositoryDiscovery,
  RepositoryWorkspace,
  Requirement,
  Reproduction,
  Review,
  RootCauseAnalysis,
  RuntimeMetadata,
  SpecCodeLink,
  SpecDelta,
  Task,
  TaskContract,
  TaskDependency,
  TaskPlan,
  TraceCorrelation,
  UserStory,
  VerificationObligation,
  Worktree,
} from "@/lib/contracts/entity-types";

export type FixtureRuntime = "A" | "B";

export interface World {
  runtime: FixtureRuntime;
  as_of: string;
  project: Project;
  repository: Repository;
  repositoryWorkspace: RepositoryWorkspace;
  revisions: RepositoryRevision[];
  materializations: RepositoryMaterialization[];
  executionWorkspaces: ExecutionWorkspace[];
  cycles: DeliveryCycle[];
  tasks: Task[];
  taskDependencies: TaskDependency[];
  contracts: TaskContract[];
  executions: Execution[];
  executionSnapshots: ExecutionSnapshot[];
  executionLeases: ExecutionLease[];
  runtimeMetadata: RuntimeMetadata[];
  worktrees: Worktree[];
  candidateCommits: CandidateCommit[];
  actions: ActionRequest[];
  actionResults: ActionResult[];
  artifacts: Artifact[];
  modelCalls: ModelCall[];
  ics: IntegrationCandidate[];
  icCommits: IntegrationCandidateCommit[];
  gates: Gate[];
  findings: Finding[];
  evidence: Evidence[];
  obligations: VerificationObligation[];
  acceptanceCoverage: AcceptanceCoverage[];
  reviews: Review[];
  approvals: Approval[];
  releases: Release[];
  releaseManifests: ReleaseManifest[];
  eligibilityByCycle: ReleaseEligibilityEvaluation[];
  events: DomainEvent[];
  productSources: ProductSource[];
  capabilities: Capability[];
  features: Feature[];
  featureSpecs: FeatureSpec[];
  requirements: Requirement[];
  userStories: UserStory[];
  knowledgeItems: KnowledgeItem[];
  acceptanceCriteria: AcceptanceCriterion[];
  architecture: Architecture[];
  implementationSpecs: ImplementationSpec[];
  specDeltas: SpecDelta[];
  taskPlans: TaskPlan[];
  indexVersions: CodeIndexVersion[];
  indexPointer: IndexPointer;
  codeEntities: CodeEntity[];
  codeRelations: CodeRelation[];
  codeEntityChanges: CodeEntityChange[];
  specCodeLinks: SpecCodeLink[];
  sampleLineage: LineageGraph;
  discovery: RepositoryDiscovery | null;
  observedBehaviors: ObservedBehavior[];
  recoveredSpecs: RecoveredSpec[];
  promotions: PromotionDecision[];
  baselines: BehavioralBaseline[];
  baselineSet: BaselineSet | null;
  readiness: ReadinessAssessment | null;
  impactAssessments: ImpactAssessment[];
  defect: Defect | null;
  reproductions: Reproduction[];
  trace: TraceCorrelation | null;
  rca: RootCauseAnalysis | null;
  connectors: ConnectorConfig[];
  inboundEvents: InboundEvent[];
  connectorActions: ConnectorAction[];
  changeRequests: ChangeRequest[];
  controlDecisions: ControlDecision[];
  commitLedger: CommitLedgerEntry[];
  eventSeq: number;
  actorRoles: ("OPERATOR" | "APPROVER" | "VIEWER")[];
}

export function createEmptyWorld(runtime: FixtureRuntime): World {
  return {
    runtime,
    as_of: "",
    project: {
      id: "",
      key: "",
      name: "",
      readiness_state: "UNKNOWN",
    },
    repository: {
      id: "",
      project_id: "",
      key: "REPO-001",
      name: "supportdesk",
      source_type: "EXTERNAL_CLONE",
      provider: "GITHUB",
      remote_url: "https://github.com/acme/supportdesk",
      default_branch: "main",
      status: "CLONING",
      workspace_id: "",
      credential_status: "CONFIGURED",
    },
    repositoryWorkspace: {
      id: "",
      repository_id: "",
      key: "WS-001",
      workspace_type: "CANONICAL",
      storage_backend: "LOCAL_FILESYSTEM",
      logical_location: "",
      state: "PENDING",
    },
    revisions: [],
    materializations: [],
    executionWorkspaces: [],
    cycles: [],
    tasks: [],
    taskDependencies: [],
    contracts: [],
    executions: [],
    executionSnapshots: [],
    executionLeases: [],
    runtimeMetadata: [],
    worktrees: [],
    candidateCommits: [],
    actions: [],
    actionResults: [],
    artifacts: [],
    modelCalls: [],
    ics: [],
    icCommits: [],
    gates: [],
    findings: [],
    evidence: [],
    obligations: [],
    acceptanceCoverage: [],
    reviews: [],
    approvals: [],
    releases: [],
    releaseManifests: [],
    eligibilityByCycle: [],
    events: [],
    productSources: [],
    capabilities: [],
    features: [],
    featureSpecs: [],
    requirements: [],
    userStories: [],
    knowledgeItems: [],
    acceptanceCriteria: [],
    architecture: [],
    implementationSpecs: [],
    specDeltas: [],
    taskPlans: [],
    indexVersions: [],
    indexPointer: { repository_id: "", canonical_index_version_id: "" },
    codeEntities: [],
    codeRelations: [],
    codeEntityChanges: [],
    specCodeLinks: [],
    sampleLineage: {
      root_type: "CODE_ENTITY",
      root_id: "",
      direction: "REVERSE",
      nodes: [],
      edges: [],
    },
    discovery: null,
    observedBehaviors: [],
    recoveredSpecs: [],
    promotions: [],
    baselines: [],
    baselineSet: null,
    readiness: null,
    impactAssessments: [],
    defect: null,
    reproductions: [],
    trace: null,
    rca: null,
    connectors: [],
    inboundEvents: [],
    connectorActions: [],
    changeRequests: [],
    controlDecisions: [],
    commitLedger: [],
    eventSeq: 0,
    actorRoles: ["OPERATOR", "APPROVER"],
  };
}
