import type {
  AcceptanceCriterion,
  ActionRequest,
  ActionResult,
  Approval,
  BaselineSet,
  BehavioralBaseline,
  CandidateCommit,
  Capability,
  ChangeRequest,
  CodeEntity,
  CodeIndexVersion,
  CodeRelation,
  ConnectorAction,
  ConnectorConfig,
  ControlPlaneView,
  CycleOverviewView,
  ProductSource,
  Defect,
  DeliveryCycle,
  DomainEvent,
  Execution,
  ExecutionSnapshot,
  Feature,
  FeatureSpec,
  Finding,
  Gate,
  ImpactAssessment,
  ImplementationSpec,
  InboundEvent,
  IntegrationCandidate,
  LineageGraph,
  Project,
  ReadinessAssessment,
  RecoveredSpec,
  Release,
  ReleaseEligibilityEvaluation,
  Reproduction,
  RepositoryDiscovery,
  RootCauseAnalysis,
  SpecCodeLink,
  Task,
  TaskContract,
  TaskDependency,
  TraceCorrelation,
  TransitionPreview,
  Worktree,
  ExecutionWorkspace,
  ExecutionLease,
  ModelCall,
  Artifact,
  RuntimeMetadata,
  Repository,
  RepositoryWorkspace,
  RepositoryRevision,
  RepositoryMaterialization,
  CommitLedgerEntry,
  CodeEntityChange,
  Evidence,
  VerificationObligation,
  AcceptanceCoverage,
  Review,
  ReleaseManifest,
  ControlDecision,
  Requirement,
  UserStory,
  KnowledgeItem,
  ObservedBehavior,
  PromotionDecision,
  Architecture,
  TaskPlan,
  SpecDelta,
  IntegrationCandidateCommit,
} from "@/lib/contracts/entity-types";

export interface AuthService {
  me(): Promise<{
    actor_id: string;
    kind: "HUMAN" | "AGENT" | "SYSTEM" | "INTEGRATION";
    name: string;
    roles: string[];
    scopes?: string[];
  }>;
  setViewerMode(viewer: boolean): void;
}

export interface ProjectsService {
  list(): Promise<Project[]>;
  get(id: string): Promise<Project>;
  summary(projectId: string): Promise<ProjectSummaryViewCompat>;
}

/** @proposed M-26 — minimal compat shape until views land in UI */
export interface ProjectSummaryViewCompat {
  project_id: string;
  active_cycle_id?: string | null;
  active_cycle_key?: string | null;
  stage?: string | null;
  task_count: number;
  running_executions: number;
  canonical_sha?: string | null;
  released_sha?: string | null;
  current_release_key?: string | null;
  repository_id?: string | null;
  repository_status?: string | null;
  canonical_index_key?: string | null;
}

export interface DeliveryCyclesService {
  list(projectId: string): Promise<DeliveryCycle[]>;
  get(id: string): Promise<DeliveryCycle>;
  nextTransitions(cycleId: string): Promise<TransitionPreview[]>;
  events(
    cycleId: string,
    after?: number,
  ): Promise<{ items: DomainEvent[]; next_after: number | null }>;
  command(
    cycleId: string,
    command: string,
    body: { expected_state: string; payload?: unknown },
    idempotencyKey: string,
  ): Promise<unknown>;
}

export interface TasksService {
  listByCycle(cycleId: string): Promise<Task[]>;
  get(id: string): Promise<Task>;
  dag(cycleId: string): Promise<{ nodes: Task[]; edges: TaskDependency[] }>;
  contract(taskId: string): Promise<TaskContract>;
  eligibility(taskId: string): Promise<{
    eligible: boolean;
    reasons: string[];
    conditions?: Array<{ condition: string; ok: boolean; detail?: string }>;
  }>;
}

export interface ExecutionsService {
  listByTask(taskId: string): Promise<Execution[]>;
  listByCycle(cycleId: string): Promise<Execution[]>;
  get(id: string): Promise<Execution>;
  snapshot(executionId: string): Promise<ExecutionSnapshot | null>;
  worktree(executionId: string): Promise<Worktree | null>;
  workspace(executionId: string): Promise<ExecutionWorkspace | null>;
  lease(executionId: string): Promise<ExecutionLease | null>;
  runtimeMetadata(executionId: string): Promise<RuntimeMetadata | null>;
  modelCalls(executionId: string): Promise<ModelCall[]>;
  artifacts(executionId: string): Promise<Artifact[]>;
  candidateCommit(executionId: string): Promise<CandidateCommit | null>;
  actions(executionId: string): Promise<ActionRequest[]>;
}

export interface ApprovalsService {
  pending(): Promise<Approval[]>;
  decide(id: string, decision: string, note: string, idempotencyKey: string): Promise<Approval>;
}

export interface ReleaseService {
  eligibility(cycleId: string): Promise<ReleaseEligibilityEvaluation>;
  get(releaseId: string): Promise<Release>;
  list(projectId: string): Promise<Release[]>;
  forCycle(cycleId: string): Promise<Release | null>;
  manifest(releaseId: string): Promise<ReleaseManifest | null>;
}

export interface AssuranceService {
  gatesForIc(icId: string): Promise<Gate[]>;
  findings(cycleId: string): Promise<Finding[]>;
  evidence(filters: {
    ic_id?: string;
    cycle_id?: string;
    subject_id?: string;
  }): Promise<Evidence[]>;
  obligations(icId: string): Promise<VerificationObligation[]>;
  coverage(icId: string): Promise<AcceptanceCoverage[]>;
  reviews(icId: string): Promise<Review[]>;
}

export interface IntegrationService {
  listByCycle(cycleId: string): Promise<IntegrationCandidate[]>;
  get(id: string): Promise<IntegrationCandidate>;
  commits(icId: string): Promise<IntegrationCandidateCommit[]>;
}

export interface InboxService {
  list(): Promise<
    Array<{
      kind: "APPROVAL";
      id: string;
      title: string;
      why: string;
      approval: Approval;
    }>
  >;
}

export interface ViewsService {
  projectOverview(projectId: string): Promise<CycleOverviewView | null>;
  cycleOverview(cycleId: string): Promise<CycleOverviewView>;
  controlPlane(cycleId: string): Promise<ControlPlaneView>;
}

export interface ControlPlaneService {
  forCycle(cycleId: string): Promise<ControlPlaneView>;
  explain(subjectType: string, subjectId: string): Promise<ControlDecision | null>;
}

export interface CodeService {
  canonicalIndex(repositoryId: string): Promise<CodeIndexVersion | null>;
  listVersions(repositoryId: string): Promise<CodeIndexVersion[]>;
  getEntity(entityId: string): Promise<CodeEntity>;
  entities(
    indexVersionId: string,
    filters?: { file_path?: string; type?: string },
  ): Promise<CodeEntity[]>;
  byStableKey(indexVersionId: string, stableKey: string): Promise<CodeEntity | null>;
  neighbors(entityId: string, depth?: number): Promise<{ entities: CodeEntity[]; relations: CodeRelation[] }>;
  search(repositoryId: string, query: string): Promise<CodeEntity[]>;
  relations(indexVersionId: string): Promise<CodeRelation[]>;
  entityChanges(
    repositoryId: string,
    filters?: { stable_key?: string; integration_candidate_id?: string },
  ): Promise<CodeEntityChange[]>;
  versionDiff(versionA: string, versionB: string): Promise<CodeEntityChange[]>;
}

export interface LineageService {
  query(params: {
    root_type: string;
    root_id: string;
    direction: "FORWARD" | "REVERSE";
    depth?: number;
  }): Promise<LineageGraph>;
  specCodeLinks(indexVersionId: string): Promise<SpecCodeLink[]>;
}

export interface ImpactService {
  forCycle(cycleId: string): Promise<ImpactAssessment | null>;
  get(assessmentId: string): Promise<ImpactAssessment>;
}

export interface BrownfieldService {
  discovery(cycleId: string): Promise<RepositoryDiscovery | null>;
  discoverySteps(cycleId: string): Promise<RepositoryDiscovery | null>;
  observedBehaviors(cycleId: string): Promise<ObservedBehavior[]>;
  recoveredSpecs(cycleId: string): Promise<RecoveredSpec[]>;
  promotions(cycleId: string): Promise<PromotionDecision[]>;
  baselines(projectId: string): Promise<BehavioralBaseline[]>;
  baselineSet(projectId: string): Promise<BaselineSet | null>;
  readiness(cycleId: string): Promise<ReadinessAssessment | null>;
}

export interface RepositoriesService {
  forProject(projectId: string): Promise<Repository | null>;
  get(repositoryId: string): Promise<Repository>;
  workspace(repositoryId: string): Promise<RepositoryWorkspace>;
  revisions(repositoryId: string): Promise<RepositoryRevision[]>;
  materializations(repositoryId: string): Promise<RepositoryMaterialization[]>;
  executionWorkspaces(
    repositoryId: string,
    filters?: { state?: string; cycle_id?: string },
  ): Promise<ExecutionWorkspace[]>;
  commitLedger(repositoryId: string): Promise<CommitLedgerEntry[]>;
}

export interface ArtifactsService {
  get(artifactId: string): Promise<Artifact>;
  textContent(artifactId: string): Promise<string | null>;
}

export interface ActionsService {
  list(filters: {
    project_id: string;
    delivery_cycle_id?: string;
    execution_id?: string;
    status?: string;
  }): Promise<ActionRequest[]>;
  get(id: string): Promise<ActionRequest>;
  result(actionId: string): Promise<ActionResult | null>;
}

export interface DefectsService {
  get(defectId: string): Promise<Defect>;
  forCycle(cycleId: string): Promise<Defect | null>;
  reproductions(defectId: string): Promise<Reproduction[]>;
  trace(defectId: string): Promise<TraceCorrelation | null>;
  rca(defectId: string): Promise<RootCauseAnalysis | null>;
}

export interface ChangeRequestsService {
  list(projectId: string): Promise<ChangeRequest[]>;
  get(id: string): Promise<ChangeRequest>;
}

export interface ConnectorsService {
  list(projectId: string): Promise<ConnectorConfig[]>;
  inboundEvents(projectId: string): Promise<InboundEvent[]>;
  actions(projectId: string): Promise<ConnectorAction[]>;
}

export interface ProductService {
  sources(projectId: string): Promise<ProductSource[]>;
  capabilities(projectId: string): Promise<Capability[]>;
  features(projectId: string): Promise<Feature[]>;
  featureSpecs(projectId: string): Promise<FeatureSpec[]>;
  acceptanceCriteria(featureSpecId: string): Promise<AcceptanceCriterion[]>;
  requirements(featureSpecId: string): Promise<Requirement[]>;
  userStories(featureSpecId: string): Promise<UserStory[]>;
  knowledge(projectId: string, cycleId?: string): Promise<KnowledgeItem[]>;
  specDeltas(projectId: string): Promise<SpecDelta[]>;
}

export interface PlanningService {
  implementationSpecs(cycleId: string): Promise<ImplementationSpec[]>;
  architecture(projectId: string): Promise<Architecture[]>;
  taskPlans(cycleId: string): Promise<TaskPlan[]>;
}

export interface EventsService {
  forProject(projectId: string, after?: number): Promise<{ items: DomainEvent[]; next_after: number | null }>;
}

export interface OlympusServices {
  auth: AuthService;
  repositories: RepositoriesService;
  artifacts: ArtifactsService;
  projects: ProjectsService;
  deliveryCycles: DeliveryCyclesService;
  tasks: TasksService;
  executions: ExecutionsService;
  approvals: ApprovalsService;
  release: ReleaseService;
  assurance: AssuranceService;
  integration: IntegrationService;
  inbox: InboxService;
  views: ViewsService;
  controlPlane: ControlPlaneService;
  code: CodeService;
  lineage: LineageService;
  impact: ImpactService;
  brownfield: BrownfieldService;
  actions: ActionsService;
  defects: DefectsService;
  changeRequests: ChangeRequestsService;
  connectors: ConnectorsService;
  product: ProductService;
  planning: PlanningService;
  events: EventsService;
}
