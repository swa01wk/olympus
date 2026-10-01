import { OlympusApiError } from "@/lib/api/errors";
import type { OlympusServices } from "@/lib/api/olympus-services";
import type { TransitionPreview } from "@/lib/contracts/entity-types";
import { queryLineage } from "./engine/lineage-index";
import type { FixtureStore } from "./store";
import { IDS } from "./ids";
import { isExecutionActive } from "@/lib/utils/execution-active";

export function createFixtureServicesFromWorld(world: FixtureStore): {
  services: OlympusServices;
  worldRef: FixtureStore;
} {
  const eligibilityMap = world.eligibilityByCycle;
  const w = (): FixtureStore => world;

  const services: OlympusServices = {
  repositories: {
    async forProject(projectId: string) {
      const repo = w().repository;
      return repo.project_id === projectId ? repo : null;
    },
    async get(repositoryId: string) {
      if (w().repository.id !== repositoryId) throw new OlympusApiError(404, "NOT_FOUND", "Repository not found");
      return w().repository;
    },
    async workspace(repositoryId: string) {
      if (w().repositoryWorkspace.repository_id !== repositoryId) {
        throw new OlympusApiError(404, "NOT_FOUND", "Workspace not found");
      }
      return w().repositoryWorkspace;
    },
    async revisions(repositoryId: string) {
      return w().revisions.filter((r) => r.repository_id === repositoryId);
    },
    async materializations(repositoryId: string) {
      return w().materializations.filter((m) => m.repository_id === repositoryId);
    },
    async executionWorkspaces(repositoryId, filters) {
      return w().executionWorkspaces.filter((exw) => {
        if (exw.repository_id !== repositoryId) return false;
        if (filters?.state && exw.state !== filters.state) return false;
        if (filters?.cycle_id) {
          const ex = w().executions.find((e) => e.id === exw.execution_id);
          if (ex?.delivery_cycle_id !== filters.cycle_id) return false;
        }
        return true;
      });
    },
    async commitLedger(repositoryId: string) {
      return w().commitLedger.length ? w().commitLedger : w().commitLedger;
    },
  },
  artifacts: {
    async get(artifactId: string) {
      const a = w().artifacts.find((x) => x.id === artifactId);
      if (!a) throw new OlympusApiError(404, "NOT_FOUND", "Artifact not found");
      return a;
    },
    async textContent(artifactId: string) {
      const a = w().artifacts.find((x) => x.id === artifactId);
      return a?.storage_ref ?? null;
    },
  },
  auth: {
    async me() {
      return {
        actor_id: IDS.actorLead,
        kind: "HUMAN" as const,
        name: "lead",
        roles: w().actorRoles,
        scopes: ["read", "operate", "approve"],
      };
    },
    setViewerMode(viewer: boolean) {
      w().actorRoles = viewer ? ["VIEWER"] : ["OPERATOR", "APPROVER"];
    },
  },
  projects: {
    async list() {
      return [w().project];
    },
    async get(id: string) {
      if (w().project.id !== id) throw new OlympusApiError(404, "NOT_FOUND", "Project not found");
      return w().project;
    },
    async summary(projectId: string) {
      const cycles = w().cycles.filter((c) => c.project_id === projectId);
      const active = cycles.find((c) => c.state === "DEVELOPMENT") ?? cycles.at(-1);
      const running = w().executions.filter((e) => e.status === "STARTED").length;
      const released = w().releases.find((r) => r.status === "RELEASED");
      return {
        project_id: projectId,
        active_cycle_id: active?.id ?? null,
        active_cycle_key: active?.key ?? null,
        stage: active?.state ?? null,
        task_count: w().tasks.filter((t) => t.delivery_cycle_id === active?.id).length,
        running_executions: running,
        canonical_sha: w().repository.canonical_commit ?? w().indexPointer.released_commit_sha ?? null,
        released_sha: w().repository.released_commit ?? null,
        current_release_key: released?.key ?? null,
        repository_id: w().repository.id,
        repository_status: w().repository.status,
        canonical_index_key:
          w().indexVersions.find((v) => v.id === w().indexPointer.canonical_index_version_id)?.key ??
          null,
      };
    },
  },
  deliveryCycles: {
    async list(projectId: string) {
      return w().cycles.filter((c) => c.project_id === projectId);
    },
    async get(id: string) {
      const c = w().cycles.find((x) => x.id === id);
      if (!c) throw new OlympusApiError(404, "NOT_FOUND", "Cycle not found");
      return {
        ...c,
        allowed_commands: await services.deliveryCycles.nextTransitions(id).then((t) =>
          t.map((p) => ({
            command: p.command,
            allowed: p.allowed,
            guard_results: p.guard_results,
          })),
        ),
      };
    },
    async nextTransitions(cycleId: string): Promise<TransitionPreview[]> {
      const c = w().cycles.find((x) => x.id === cycleId);
      if (!c) return [];
      if (c.state === "DEVELOPMENT") {
        return [
          {
            command: "start_integration",
            target_state: "INTEGRATION",
            allowed: false,
            guard_results: [
              { guard: "all_code_tasks_completed", ok: false, reason: "TASK-223 BLOCKED" },
            ],
          },
        ];
      }
      if (c.state === "ASSURANCE") {
        return [
          {
            command: "start_release",
            target_state: "RELEASE",
            allowed: false,
            guard_results: [{ guard: "required_gates_pass", ok: false, reason: "Sentinel FAIL" }],
          },
        ];
      }
      return [];
    },
    async events(cycleId: string, after?: number) {
      const items = w().events.filter(
        (e) => e.delivery_cycle_id === cycleId && (after == null || e.sequence > after),
      );
      const last = items.at(-1);
      return { items, next_after: last?.sequence ?? null };
    },
    async command(cycleId, command, body, _idem) {
      const c = w().cycles.find((x) => x.id === cycleId);
      if (!c) throw new OlympusApiError(404, "NOT_FOUND", "Cycle not found");
      if (c.state !== body.expected_state) {
        throw new OlympusApiError(409, "StateConflict", "State changed", [], c.state);
      }
      throw new OlympusApiError(422, "FIXTURE_NO_SCRIPT", `No fixture script for ${command}`);
    },
  },
  tasks: {
    async listByCycle(cycleId: string) {
      return w().tasks.filter((t) => t.delivery_cycle_id === cycleId);
    },
    async get(id: string) {
      const t = w().tasks.find((x) => x.id === id);
      if (!t) throw new OlympusApiError(404, "NOT_FOUND", "Task not found");
      return t;
    },
    async dag(cycleId: string) {
      const nodes = await services.tasks.listByCycle(cycleId);
      const edges = w().taskDependencies.filter(
        (d) => nodes.some((n) => n.id === d.task_id),
      );
      return { nodes, edges };
    },
    async contract(taskId: string) {
      const c = w().contracts.find((x) => x.task_id === taskId);
      if (!c) throw new OlympusApiError(404, "NOT_FOUND", "Contract not found");
      return c;
    },
    async eligibility(taskId: string) {
      const t = await services.tasks.get(taskId);
      if (t.status === "BLOCKED" && t.blocked_reason) {
        const decision = w().controlDecisions.find((d) => d.subject_id === taskId);
        return {
          eligible: false,
          reasons: [t.blocked_reason],
          conditions: decision?.conditions.map((c) => ({
            condition: c.name,
            ok: c.ok,
            detail: c.detail,
          })),
        };
      }
      return { eligible: true, reasons: [] as string[] };
    },
  },
  executions: {
    async listByTask(taskId: string) {
      return w().executions.filter((e) => e.task_id === taskId);
    },
    async get(id: string) {
      const e = w().executions.find((x) => x.id === id);
      if (!e) throw new OlympusApiError(404, "NOT_FOUND", "Execution not found");
      return e;
    },
    async listByCycle(cycleId: string) {
      return w().executions.filter((e) => e.delivery_cycle_id === cycleId);
    },
    async snapshot(executionId: string) {
      return w().executionSnapshots.find((snap) => snap.execution_id === executionId) ?? null;
    },
    async worktree(executionId: string) {
      return w().worktrees.find((wt) => wt.execution_id === executionId) ?? null;
    },
    async workspace(executionId: string) {
      return w().executionWorkspaces.find((exw) => exw.execution_id === executionId) ?? null;
    },
    async lease(executionId: string) {
      return w().executionLeases.find((l) => l.execution_id === executionId) ?? null;
    },
    async runtimeMetadata(executionId: string) {
      return w().runtimeMetadata.find((m) => m.execution_id === executionId) ?? null;
    },
    async modelCalls(executionId: string) {
      return w().modelCalls.filter((m) => m.execution_id === executionId);
    },
    async artifacts(executionId: string) {
      return w().artifacts.filter((a) => a.execution_id === executionId);
    },
    async candidateCommit(executionId: string) {
      return w().candidateCommits.find((c) => c.execution_id === executionId) ?? null;
    },
    async actions(executionId: string) {
      return w().actions.filter((a) => a.execution_id === executionId);
    },
  },
  approvals: {
    async pending() {
      return w().approvals.filter((a) => a.status === "PENDING");
    },
    async decide(id, decision, _note, _idem) {
      const a = w().approvals.find((x) => x.id === id);
      if (!a) throw new OlympusApiError(404, "NOT_FOUND", "Approval not found");
      if (w().actorRoles.includes("VIEWER")) {
        throw new OlympusApiError(403, "FORBIDDEN", "VIEWER cannot approve");
      }
      a.status = decision as typeof a.status;
      if (decision === "APPROVED" && a.key) {
        const { tryAdvanceOnApproval } = await import("./controller");
        tryAdvanceOnApproval(a.key);
      }
      w().events.push({
        id: `approval-${a.id}-${decision}`,
        sequence: ++world.eventSeq,
        event_type: "approval.decided",
        aggregate_type: "approval",
        aggregate_id: a.id,
        project_id: a.project_id,
        delivery_cycle_id: a.delivery_cycle_id,
        payload: { decision },
        correlation_id: `corr-approval-${a.id}`,
        occurred_at: world.as_of,
      });
      return a;
    },
  },
  release: {
    async eligibility(cycleId: string) {
      const ev = eligibilityMap.get(cycleId);
      if (!ev) {
        throw new OlympusApiError(
          404,
          "NOT_EVALUATED",
          "Release eligibility not evaluated for this cycle",
        );
      }
      return ev;
    },
    async get(releaseId: string) {
      const r = w().releases.find((x) => x.id === releaseId);
      if (!r) throw new OlympusApiError(404, "NOT_FOUND", "Release not found");
      return r;
    },
    async list(projectId: string) {
      return w().releases.filter((r) => r.project_id === projectId);
    },
    async forCycle(cycleId: string) {
      return w().releases.find((r) => r.delivery_cycle_id === cycleId) ?? null;
    },
    async manifest(releaseId: string) {
      return w().releaseManifests.find((m) => m.release_id === releaseId) ?? null;
    },
  },
  assurance: {
    async gatesForIc(icId: string) {
      return w().gates.filter((g) => g.integration_candidate_id === icId);
    },
    async findings(cycleId: string) {
      return w().findings.filter((f) => f.delivery_cycle_id === cycleId);
    },
    async evidence(filters) {
      return w().evidence.filter((e) => {
        if (filters.ic_id && e.integration_candidate_id !== filters.ic_id) return false;
        if (filters.cycle_id && e.delivery_cycle_id !== filters.cycle_id) return false;
        if (filters.subject_id && e.subject_id !== filters.subject_id) return false;
        return true;
      });
    },
    async obligations(icId: string) {
      return w().obligations.filter((o) => o.integration_candidate_id === icId);
    },
    async coverage(icId: string) {
      return w().acceptanceCoverage.filter((c) =>
        w().obligations.some((o) => o.integration_candidate_id === icId && o.id === c.obligation_id),
      );
    },
    async reviews(icId: string) {
      return w().reviews.filter((r) => r.integration_candidate_id === icId);
    },
  },
  integration: {
    async listByCycle(cycleId: string) {
      return w().ics.filter((ic) => ic.delivery_cycle_id === cycleId);
    },
    async get(id: string) {
      const ic = w().ics.find((x) => x.id === id);
      if (!ic) throw new OlympusApiError(404, "NOT_FOUND", "IC not found");
      return ic;
    },
    async commits(icId: string) {
      return w().icCommits.filter((c) => c.integration_candidate_id === icId);
    },
  },
  inbox: {
    async list() {
      const approvals = await services.approvals.pending();
      return approvals.map((a) => ({
        kind: "APPROVAL" as const,
        id: a.id,
        title: `${a.approval_type} ${a.key}`,
        why: "Human approval required",
        approval: a,
      }));
    },
  },
  views: {
    async projectOverview(projectId: string) {
      const cycle = w().cycles.find((c) => c.project_id === projectId && c.state === "DEVELOPMENT");
      if (!cycle) return null;
      return services.views.cycleOverview(cycle.id);
    },
    async cycleOverview(cycleId: string) {
      const c = w().cycles.find((x) => x.id === cycleId);
      if (!c) throw new OlympusApiError(404, "NOT_FOUND", "Cycle not found");
      const ic = w().ics.find((i) => i.delivery_cycle_id === cycleId && i.status !== "SUPERSEDED");
      return {
        delivery_cycle_id: c.id,
        key: c.key,
        state: c.state,
        running_executions: w().executions.filter(
          (e) => e.delivery_cycle_id === cycleId && e.status === "STARTED",
        ).length,
        blocked_tasks: w().tasks.filter(
          (t) => t.delivery_cycle_id === cycleId && t.status === "BLOCKED",
        ).length,
        pending_approvals: w().approvals.filter(
          (a) => a.delivery_cycle_id === cycleId && a.status === "PENDING",
        ).length,
        integration_candidate_key: ic?.key ?? null,
      };
    },
    async controlPlane(cycleId: string) {
      return services.controlPlane.forCycle(cycleId);
    },
  },
  controlPlane: {
    async forCycle(cycleId: string) {
      const blocked = w().tasks.some(
        (t) => t.delivery_cycle_id === cycleId && t.status === "BLOCKED",
      );
      const sentinelFail = w().gates.some(
        (g) => g.delivery_cycle_id === cycleId && g.gate_type === "SENTINEL" && g.status === "FAIL",
      );
      return {
        delivery_cycle_id: cycleId,
        scheduler: { queued_tasks: blocked ? 0 : 1 },
        execution_manager: {
          running: w().executions.filter(
            (e) => e.delivery_cycle_id === cycleId && e.status === "STARTED",
          ).length,
        },
        policy: { denied_actions: w().actions.filter((a) => a.status === "DENIED").length },
        integration: {
          active_ic: w().ics.find((i) => i.delivery_cycle_id === cycleId && i.status === "CREATED")
            ?.key,
        },
        assurance: { sentinel_fail: sentinelFail },
        release: {
          eligible: eligibilityMap.get(cycleId)?.eligible ?? null,
        },
      };
    },
    async explain(subjectType: string, subjectId: string) {
      return (
        w().controlDecisions.find(
          (d) => d.subject_type === subjectType && d.subject_id === subjectId,
        ) ?? null
      );
    },
  },
  code: {
    async canonicalIndex(repositoryId: string) {
      const st = w();
      if (st.indexPointer.repository_id !== repositoryId) return null;
      return (
        st.indexVersions.find((v) => v.id === st.indexPointer.canonical_index_version_id) ?? null
      );
    },
    async listVersions(repositoryId: string) {
      return w().indexVersions.filter((v) => v.repository_id === repositoryId);
    },
    async getEntity(entityId: string) {
      const e = w().codeEntities.find((x) => x.id === entityId);
      if (!e) throw new OlympusApiError(404, "NOT_FOUND", "Code entity not found");
      return e;
    },
    async search(repositoryId: string, query: string) {
      const q = query.toLowerCase();
      return w().codeEntities.filter(
        (e) =>
          w().indexVersions.some((v) => v.repository_id === repositoryId && v.id === e.index_version_id) &&
          (e.name.toLowerCase().includes(q) || e.stable_key.toLowerCase().includes(q)),
      );
    },
    async relations(indexVersionId: string) {
      return w().codeRelations.filter((r) => r.index_version_id === indexVersionId);
    },
    async entities(indexVersionId, filters) {
      return w().codeEntities.filter((e) => {
        if (e.index_version_id !== indexVersionId) return false;
        if (filters?.file_path && e.file_path !== filters.file_path) return false;
        if (filters?.type && e.type !== filters.type) return false;
        return true;
      });
    },
    async byStableKey(indexVersionId: string, stableKey: string) {
      return (
        w().codeEntities.find(
          (e) => e.index_version_id === indexVersionId && e.stable_key === stableKey,
        ) ?? null
      );
    },
    async neighbors(entityId: string, depth = 1) {
      const rels = w().codeRelations.filter(
        (r) => r.from_entity_id === entityId || r.to_entity_id === entityId,
      );
      const ids = new Set<string>([entityId]);
      for (const r of rels) {
        ids.add(r.from_entity_id);
        ids.add(r.to_entity_id);
      }
      return {
        entities: w().codeEntities.filter((e) => ids.has(e.id)).slice(0, 200),
        relations: rels.slice(0, depth * 50),
      };
    },
    async entityChanges(repositoryId, filters) {
      return w().codeEntityChanges.filter((c) => {
        if (c.repository_id && c.repository_id !== repositoryId) return false;
        if (filters?.stable_key && c.entity_stable_key !== filters.stable_key) return false;
        if (
          filters?.integration_candidate_id &&
          c.integration_candidate_id !== filters.integration_candidate_id
        )
          return false;
        return true;
      });
    },
    async versionDiff(versionA: string, versionB: string) {
      return w().codeEntityChanges.filter(
        (c) => c.from_index_version_id === versionA || c.to_index_version_id === versionB,
      );
    },
  },
  lineage: {
    async query(params) {
      return queryLineage(w() as unknown as import("./engine/world").World, params);
    },
    async specCodeLinks(indexVersionId: string) {
      return w().specCodeLinks.filter((l) => l.index_version_id === indexVersionId);
    },
  },
  impact: {
    async forCycle(cycleId: string) {
      return w().impactAssessments.find((a) => a.delivery_cycle_id === cycleId) ?? null;
    },
    async get(assessmentId: string) {
      const a = w().impactAssessments.find((x) => x.id === assessmentId);
      if (!a) throw new OlympusApiError(404, "NOT_FOUND", "Impact assessment not found");
      return a;
    },
  },
  brownfield: {
    async discovery(cycleId: string) {
      const d = w().discovery;
      if (!d || d.delivery_cycle_id !== cycleId) return null;
      return d;
    },
    async discoverySteps(cycleId: string) {
      const d = w().discovery;
      return d?.delivery_cycle_id === cycleId ? d : null;
    },
    async promotions(cycleId: string) {
      return w().promotions.filter((p) => p.delivery_cycle_id === cycleId);
    },
    async observedBehaviors(cycleId: string) {
      return w().observedBehaviors.filter((o) => o.delivery_cycle_id === cycleId);
    },
    async recoveredSpecs(cycleId: string) {
      return w().recoveredSpecs.filter((r) => r.delivery_cycle_id === cycleId);
    },
    async baselines(projectId: string) {
      return w().baselines.filter((b) => b.project_id === projectId);
    },
    async baselineSet(projectId: string) {
      const bs = w().baselineSet;
      return bs && bs.project_id === projectId ? bs : null;
    },
    async readiness(cycleId: string) {
      const r = w().readiness;
      return r && r.delivery_cycle_id === cycleId ? r : null;
    },
  },
  actions: {
    async list(filters) {
      return w().actions.filter((a) => {
        if (a.project_id !== filters.project_id) return false;
        if (filters.delivery_cycle_id && a.delivery_cycle_id !== filters.delivery_cycle_id) return false;
        if (filters.execution_id && a.execution_id !== filters.execution_id) return false;
        if (filters.status && a.status !== filters.status) return false;
        return true;
      });
    },
    async get(id: string) {
      const a = w().actions.find((x) => x.id === id);
      if (!a) throw new OlympusApiError(404, "NOT_FOUND", "Action not found");
      return a;
    },
    async result(actionId: string) {
      return w().actionResults.find((r) => r.action_request_id === actionId) ?? null;
    },
  },
  defects: {
    async get(defectId: string) {
      const d = w().defect;
      if (!d || d.id !== defectId) throw new OlympusApiError(404, "NOT_FOUND", "Defect not found");
      return d;
    },
    async forCycle(cycleId: string) {
      const d = w().defect;
      return d && d.delivery_cycle_id === cycleId ? d : null;
    },
    async reproductions(defectId: string) {
      const d = w().defect;
      if (!d || d.id !== defectId) return [];
      return w().reproductions;
    },
    async trace(defectId: string) {
      const d = w().defect;
      if (!d || d.id !== defectId) return null;
      return w().trace;
    },
    async rca(defectId: string) {
      const d = w().defect;
      if (!d || d.id !== defectId) return null;
      return w().rca;
    },
  },
  changeRequests: {
    async list(projectId: string) {
      return w().changeRequests.filter((c) => c.project_id === projectId);
    },
    async get(id: string) {
      const c = w().changeRequests.find((x) => x.id === id);
      if (!c) throw new OlympusApiError(404, "NOT_FOUND", "Change request not found");
      return c;
    },
  },
  connectors: {
    async list(projectId: string) {
      return w().connectors.filter((c) => c.project_id === projectId);
    },
    async inboundEvents(projectId: string) {
      return w().inboundEvents.filter((e) => e.project_id === projectId);
    },
    async actions(projectId: string) {
      return w().connectorActions.filter((a) =>
        w().connectors.some((c) => c.project_id === projectId && c.id === a.connector_id),
      );
    },
  },
  product: {
    async sources(projectId: string) {
      return w().productSources.filter((p) => p.project_id === projectId);
    },
    async capabilities(projectId: string) {
      return w().capabilities.filter((c) => c.project_id === projectId);
    },
    async features(projectId: string) {
      return w().features.filter((f) => f.project_id === projectId);
    },
    async featureSpecs(projectId: string) {
      const featureIds = new Set(
        w().features.filter((f) => f.project_id === projectId).map((f) => f.id),
      );
      return w().featureSpecs.filter((fs) => featureIds.has(fs.feature_id));
    },
    async acceptanceCriteria(featureSpecId: string) {
      return w().acceptanceCriteria.filter((ac) => ac.feature_spec_id === featureSpecId);
    },
    async requirements(featureSpecId: string) {
      return w().requirements.filter((r) => r.feature_spec_id === featureSpecId);
    },
    async userStories(featureSpecId: string) {
      return w().userStories.filter((u) => u.feature_spec_id === featureSpecId);
    },
    async knowledge(projectId: string, cycleId?: string) {
      return w().knowledgeItems.filter(
        (k) =>
          k.project_id === projectId &&
          (cycleId == null || k.delivery_cycle_id === cycleId || !k.delivery_cycle_id),
      );
    },
    async specDeltas(_projectId: string) {
      return w().specDeltas;
    },
  },
  planning: {
    async implementationSpecs(cycleId: string) {
      return w().implementationSpecs.filter((spec) => spec.delivery_cycle_id === cycleId);
    },
    async architecture(projectId: string) {
      return w().architecture.filter((a) => a.project_id === projectId);
    },
    async taskPlans(cycleId: string) {
      return w().taskPlans.filter((p) => p.delivery_cycle_id === cycleId);
    },
  },
  events: {
    async forProject(projectId: string, after?: number) {
      const items = w().events.filter(
        (e) => e.project_id === projectId && (after == null || e.sequence > after),
      );
      const last = items.at(-1);
      return { items, next_after: last?.sequence ?? null };
    },
  },
};

  return { services, worldRef: world };
}
