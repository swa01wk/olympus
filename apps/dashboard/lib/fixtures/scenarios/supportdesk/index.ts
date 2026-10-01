import type {
  AcceptanceCriterion,
  ActionRequest,
  ActionResult,
  Approval,
  Architecture,
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
  IndexPointer,
  IntegrationCandidate,
  LineageGraph,
  ProductSource,
  Project,
  ReadinessAssessment,
  RecoveredSpec,
  Release,
  ReleaseEligibilityEvaluation,
  Reproduction,
  RepositoryDiscovery,
  RootCauseAnalysis,
  SpecCodeLink,
  SpecDelta,
  Task,
  TaskContract,
  TaskDependency,
  TaskPlan,
  TraceCorrelation,
  Worktree,
} from "@/lib/contracts/entity-types";
import { buildActions } from "./actions";
import { buildAssurance } from "./assurance";
import { buildBrownfield } from "./brownfield";
import { buildCodeIndex } from "./code-index";
import { buildDefect } from "./defect";
import { buildEvents } from "./events";
import { buildExecutions } from "./executions";
import { buildImpact } from "./impact";
import { buildIntegrationCore } from "./integration";
import { buildIntegrations } from "./integrations";
import { buildPlanning } from "./planning";
import { buildProduct } from "./product";
import { buildTasks } from "./tasks";
import { buildTraceLinks } from "./trace-links";

export interface SupportDeskSeed {
  project: Project;
  cycles: DeliveryCycle[];
  tasks: Task[];
  taskDependencies: TaskDependency[];
  contracts: TaskContract[];
  executions: Execution[];
  executionSnapshots: ExecutionSnapshot[];
  worktrees: Worktree[];
  candidateCommits: CandidateCommit[];
  actions: ActionRequest[];
  actionResults: ActionResult[];
  ics: IntegrationCandidate[];
  gates: Gate[];
  findings: Finding[];
  approvals: Approval[];
  releases: Release[];
  eligibilityByCycle: ReleaseEligibilityEvaluation[];
  events: DomainEvent[];
  productSources: ProductSource[];
  capabilities: Capability[];
  features: Feature[];
  featureSpecs: FeatureSpec[];
  acceptanceCriteria: AcceptanceCriterion[];
  architecture: Architecture[];
  implementationSpecs: ImplementationSpec[];
  specDeltas: SpecDelta[];
  taskPlans: TaskPlan[];
  indexVersions: CodeIndexVersion[];
  indexPointer: IndexPointer;
  codeEntities: CodeEntity[];
  codeRelations: CodeRelation[];
  specCodeLinks: SpecCodeLink[];
  sampleLineage: LineageGraph;
  discovery: RepositoryDiscovery;
  recoveredSpecs: RecoveredSpec[];
  baselines: BehavioralBaseline[];
  baselineSet: BaselineSet;
  readiness: ReadinessAssessment;
  impactAssessments: ImpactAssessment[];
  defect: Defect;
  reproductions: Reproduction[];
  trace: TraceCorrelation;
  rca: RootCauseAnalysis;
  connectors: ConnectorConfig[];
  inboundEvents: InboundEvent[];
  connectorActions: ConnectorAction[];
  changeRequests: ChangeRequest[];
}

export function buildSupportDeskChained(): SupportDeskSeed {
  const core = buildIntegrationCore();
  const { dependencies: taskDependencies, ...taskBundle } = buildTasks();
  const { snapshots: executionSnapshots, ...execBundle } = buildExecutions();
  const actionBundle = buildActions();
  const assurance = buildAssurance();
  const product = buildProduct();
  const planning = buildPlanning();
  const code = buildCodeIndex();
  const trace = buildTraceLinks();
  const brownfield = buildBrownfield();
  const impact = buildImpact();
  const defectBundle = buildDefect();
  const integrations = buildIntegrations();
  const { events } = buildEvents();

  return {
    ...core,
    ...taskBundle,
    taskDependencies,
    ...execBundle,
    executionSnapshots,
    ...actionBundle,
    ...assurance,
    events,
    ...product,
    ...planning,
    indexVersions: code.indexVersions,
    indexPointer: code.pointer,
    codeEntities: code.codeEntities,
    codeRelations: code.codeRelations,
    specCodeLinks: trace.specCodeLinks,
    sampleLineage: trace.sampleLineage,
    discovery: brownfield.discovery,
    recoveredSpecs: brownfield.recoveredSpecs,
    baselines: brownfield.baselines,
    baselineSet: brownfield.baselineSet,
    readiness: brownfield.readiness,
    impactAssessments: impact.impactAssessments,
    defect: defectBundle.defect,
    reproductions: defectBundle.reproductions,
    trace: defectBundle.trace,
    rca: defectBundle.rca,
    connectors: integrations.connectors,
    inboundEvents: integrations.inboundEvents,
    connectorActions: integrations.connectorActions,
    changeRequests: integrations.changeRequests,
  };
}
