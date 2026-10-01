import { buildSupportDeskChained } from "../scenarios/supportdesk";
import type { SupportDeskSeed } from "../scenarios/supportdesk";
import { IDS } from "../ids";
import { SHAS } from "../supportdesk/shas";
import { at, resetClock } from "./clock";
import type { World } from "./world";
import { fid } from "./deterministic-id";
import type {
  CommitLedgerEntry,
  ControlDecision,
  ExecutionWorkspace,
  Repository,
  RepositoryRevision,
  RepositoryWorkspace,
} from "@/lib/contracts/entity-types";

/** Maps the static chained seed into World shape + repository materialization model (Runtime B, FC@05 default). */
export function worldFromLegacyChained(): World {
  resetClock("B", 120);
  const seed = buildSupportDeskChained();
  const projectId = seed.project.id;
  const repoId = IDS.repo;
  const wsId = fid("workspace", "WS-001");

  const repository: Repository = {
    id: repoId,
    project_id: projectId,
    key: "REPO-001",
    name: "supportdesk",
    source_type: "EXTERNAL_CLONE",
    provider: "GITHUB",
    remote_url: "https://github.com/acme/supportdesk",
    default_branch: "main",
    registered_sha: SHAS.r1Integrated,
    canonical_commit: SHAS.r1Integrated,
    released_commit: SHAS.r1Integrated,
    status: "READY",
    workspace_id: wsId,
    credential_ref: "env:SUPPORTDESK_GITHUB",
    credential_status: "CONFIGURED",
  };

  const repositoryWorkspace: RepositoryWorkspace = {
    id: wsId,
    repository_id: repoId,
    key: "WS-001",
    workspace_type: "CANONICAL",
    storage_backend: "LOCAL_FILESYSTEM",
    logical_location: `projects/${projectId}/repo`,
    materialized_commit: SHAS.r1Integrated,
    state: "READY",
  };

  const revisions: RepositoryRevision[] = [
    {
      id: fid("revision", "1"),
      repository_id: repoId,
      sequence: 1,
      commit_sha: SHAS.r1Integrated,
      cause: "MATERIALIZED",
      created_at: at(120),
    },
  ];

  const executionWorkspaces: ExecutionWorkspace[] = seed.worktrees.map((wt) => {
    const ex = seed.executions.find((e) => e.id === wt.execution_id)!;
    return {
      id: fid("exws", ex.key),
      key: ex.key,
      execution_id: wt.execution_id,
      repository_id: repoId,
      type: "GIT_WORKTREE",
      mode: "WRITABLE",
      base_commit: wt.base_sha,
      logical_location: `projects/${projectId}/worktrees/${ex.key}`,
      branch: wt.branch.startsWith("olympus/") ? wt.branch : `olympus/${ex.key}`,
      state: wt.status === "ACTIVE" ? "ACTIVE" : "REMOVED",
      uncommitted_files:
        ex.key === "EX-551"
          ? [{ path: "app/models/ticket.py", change_type: "MODIFIED" }]
          : ex.key === "EX-552"
            ? [
                { path: "app/api/tickets.py", change_type: "MODIFIED" },
                { path: "app/schemas/ticket.py", change_type: "MODIFIED" },
              ]
            : [],
    };
  });

  const worktrees = seed.worktrees.map((wt) => ({
    ...wt,
    path: undefined,
    logical_location: executionWorkspaces.find((w) => w.execution_id === wt.execution_id)
      ?.logical_location,
    branch: executionWorkspaces.find((w) => w.execution_id === wt.execution_id)?.branch ?? wt.branch,
    mode: "WRITABLE",
  }));

  const controlDecisions: ControlDecision[] = [
    {
      id: fid("decision", "task-223-blocked"),
      question_kind: "TASK_BLOCKED",
      subject_type: "task",
      subject_id: IDS.taskBlocked,
      subject_key: "TASK-223",
      outcome: "BLOCKED",
      conditions: [
        { name: "repository_ready", ok: true, detail: "Repository READY" },
        { name: "dependency_complete", ok: false, detail: "DEPENDENCY_INCOMPLETE:TASK-222" },
      ],
      source_endpoint: "GET /tasks/{id}/eligibility",
    },
    {
      id: fid("decision", "integration-unavailable"),
      question_kind: "INTEGRATION_UNAVAILABLE",
      subject_type: "delivery_cycle",
      subject_id: IDS.dc003,
      subject_key: "DC-003",
      outcome: "DENIED",
      conditions: [
        {
          name: "all_code_tasks_completed",
          ok: false,
          detail: "TASK-223 BLOCKED",
          refs: [{ type: "task", id: IDS.taskBlocked, key: "TASK-223" }],
        },
      ],
      source_endpoint: "GET /delivery-cycles/{id}/next-transitions",
    },
  ];

  const commitLedger: CommitLedgerEntry[] = [
    {
      kind: "CANONICAL_REVISION",
      sha: SHAS.r1Integrated,
      label: "73fb91d",
      sequence: 1,
      cause: "MATERIALIZED",
      created_at: revisions[0]!.created_at,
    },
    ...seed.candidateCommits.map((c) => {
      const ex = seed.executions.find((e) => e.id === c.execution_id);
      return {
        kind: "CANDIDATE" as const,
        sha: c.sha,
        execution_key: ex?.key,
        branch: ex ? `olympus/${ex.key}` : undefined,
        base_sha: c.base_sha,
        included_in_ic: false,
      };
    }),
  ];

  const world: World = {
    runtime: "B",
    as_of: at(500),
    project: seed.project,
    repository,
    repositoryWorkspace,
    revisions,
    materializations: [],
    executionWorkspaces,
    cycles: seed.cycles,
    tasks: seed.tasks,
    taskDependencies: seed.taskDependencies,
    contracts: seed.contracts,
    executions: seed.executions,
    executionSnapshots: seed.executionSnapshots,
    executionLeases: [],
    runtimeMetadata: seed.executions
      .filter((e) => e.status === "STARTED")
      .map((e) => ({
        execution_id: e.id,
        runtime: "LangGraphRuntime",
        model_alias: "implementation",
        current_resource: "app/models/ticket.py",
      })),
    worktrees,
    candidateCommits: seed.candidateCommits.map((c) => ({
      ...c,
      id: fid("ccommit", c.sha),
      branch:
        executionWorkspaces.find((w) => w.execution_id === c.execution_id)?.branch ?? undefined,
    })),
    actions: seed.actions,
    actionResults: seed.actionResults,
    artifacts: [],
    modelCalls: [],
    ics: seed.ics,
    icCommits: [],
    gates: seed.gates,
    findings: seed.findings,
    evidence: [],
    obligations: [],
    acceptanceCoverage: [],
    reviews: [],
    approvals: seed.approvals,
    releases: seed.releases,
    releaseManifests: [],
    eligibilityByCycle: seed.eligibilityByCycle,
    events: seed.events.map((e, i) => ({ ...e, sequence: i + 1 })),
    productSources: seed.productSources,
    capabilities: seed.capabilities,
    features: seed.features,
    featureSpecs: seed.featureSpecs,
    requirements: [],
    userStories: [],
    knowledgeItems: [],
    acceptanceCriteria: seed.acceptanceCriteria,
    architecture: seed.architecture,
    implementationSpecs: seed.implementationSpecs,
    specDeltas: seed.specDeltas,
    taskPlans: seed.taskPlans,
    indexVersions: seed.indexVersions.map((v) => ({
      ...v,
      key: v.scope_ref.startsWith("IC") ? `CODEIDX-${v.scope_ref}` : v.scope_ref,
    })),
    indexPointer: seed.indexPointer,
    codeEntities: seed.codeEntities,
    codeRelations: seed.codeRelations,
    codeEntityChanges: [],
    specCodeLinks: seed.specCodeLinks,
    sampleLineage: seed.sampleLineage,
    discovery: seed.discovery,
    observedBehaviors: [],
    recoveredSpecs: seed.recoveredSpecs,
    promotions: [],
    baselines: seed.baselines,
    baselineSet: seed.baselineSet,
    readiness: seed.readiness,
    impactAssessments: seed.impactAssessments,
    defect: seed.defect,
    reproductions: seed.reproductions,
    trace: seed.trace,
    rca: seed.rca,
    connectors: seed.connectors,
    inboundEvents: seed.inboundEvents,
    connectorActions: seed.connectorActions,
    changeRequests: seed.changeRequests,
    controlDecisions,
    commitLedger,
    eventSeq: seed.events.length,
    actorRoles: ["OPERATOR", "APPROVER"],
  };

  patchLegacyShas(world);
  return world;
}

function patchLegacyShas(world: World) {
  const mapOldNew: Record<string, string> = {
    aaa111000000000000000000000000000000000001: SHAS.r1Integrated,
    "98af71a000000000000000000000000000000001": SHAS.dc003Base,
    c0ffee000000000000000000000000000000000551: SHAS.candidate551,
    c0ffee000000000000000000000000000000000552: SHAS.candidate552,
  };
  const replace = (s: string | null | undefined) =>
    s && mapOldNew[s] ? mapOldNew[s] : s;
  world.cycles.forEach((c) => {
    if (c.base_sha) c.base_sha = replace(c.base_sha) ?? c.base_sha;
  });
  world.candidateCommits.forEach((c) => {
    c.sha = replace(c.sha) ?? c.sha;
    c.base_sha = replace(c.base_sha) ?? c.base_sha;
    c.parent_sha = replace(c.parent_sha) ?? c.parent_sha;
  });
  world.indexVersions.forEach((v) => {
    v.commit_sha = replace(v.commit_sha) ?? v.commit_sha;
  });
  if (world.indexPointer.released_commit_sha) {
    world.indexPointer.released_commit_sha =
      replace(world.indexPointer.released_commit_sha) ?? world.indexPointer.released_commit_sha;
  }
}

export function worldFromLegacyPartial(seed: SupportDeskSeed): World {
  return worldFromLegacyChained();
}
