import type { OrchestratorProposal } from "@/src/api/types/orchestrator";

export type ProposalRouteContext = {
  projectId: string;
  cycleId: string;
  cycleState: string;
};

export type RunnableProposalRoute = {
  method: "POST";
  path: string;
  body: Record<string, unknown> | null;
  query?: Record<string, string>;
};

export type ProposalRouteResult = RunnableProposalRoute | { notRunnable: string };

function str(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function refId(proposal: OrchestratorProposal, key: string): string | undefined {
  const fromArgs = str(proposal.args[key]);
  if (fromArgs) return fromArgs;
  if (proposal.target_ref && !proposal.target_ref.includes(":")) return proposal.target_ref;
  return undefined;
}

/** Maps orchestrator PROPOSE_COMMAND payloads to REST routes (§6). */
export function routeForProposal(
  proposal: OrchestratorProposal,
  ctx: ProposalRouteContext,
): ProposalRouteResult {
  switch (proposal.command) {
    case "delivery_cycle.transition": {
      const commandName = str(proposal.args.command_name);
      if (!commandName) return { notRunnable: "Missing command_name in proposal args" };
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/commands/${commandName}`,
        body: {
          expected_state: ctx.cycleState,
          payload: (proposal.args.payload as Record<string, unknown> | null | undefined) ?? null,
        },
      };
    }
    case "create_delivery_cycle":
      return {
        method: "POST",
        path: `/projects/${ctx.projectId}/delivery-cycles`,
        body: {
          type: proposal.args.type,
          objective: proposal.args.objective,
          repository_id: proposal.args.repository_id ?? null,
        },
      };
    case "ingest_product_source":
      return {
        method: "POST",
        path: `/projects/${ctx.projectId}/sources`,
        query: { delivery_cycle_id: ctx.cycleId },
        body: {
          title: proposal.args.title,
          text: proposal.args.text,
          lineage_key: proposal.args.lineage_key ?? "default",
          source_type: proposal.args.source_type ?? "PRD",
        },
      };
    case "decompose_source": {
      const sourceId = refId(proposal, "source_id") ?? refId(proposal, "source_version_id");
      if (!sourceId) return { notRunnable: "Missing source_id in proposal" };
      return {
        method: "POST",
        path: `/sources/${sourceId}/decompose`,
        body: { delivery_cycle_id: ctx.cycleId },
      };
    }
    case "request_scope_approval":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/scope/approval-request`,
        body: { feature_spec_ids: proposal.args.feature_spec_ids ?? [] },
      };
    case "approval.request":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/approvals`,
        body: {
          approval_type: proposal.args.approval_type,
          subject_type: proposal.args.subject_type,
          subject_id: proposal.args.subject_id,
          subject_version: proposal.args.subject_version,
          subject_hash: proposal.args.subject_hash,
        },
      };
    case "task.command": {
      const taskId = refId(proposal, "task_id");
      const commandName = str(proposal.args.command_name);
      const expectedState = str(proposal.args.expected_state);
      if (!taskId || !commandName || !expectedState) {
        return { notRunnable: "Missing task_id, command_name, or expected_state" };
      }
      return {
        method: "POST",
        path: `/tasks/${taskId}/commands/${commandName}`,
        body: { expected_state: expectedState },
      };
    }
    case "create_task":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/tasks`,
        body: {
          title: proposal.args.title,
          work_type: proposal.args.work_type,
          origin: proposal.args.origin ?? "CONTROL_PLANE",
          priority: proposal.args.priority ?? 100,
        },
      };
    case "intake_change_request":
      return {
        method: "POST",
        path: `/projects/${ctx.projectId}/change-requests`,
        body: {
          title: proposal.args.title,
          description: proposal.args.description,
          external_ref: proposal.args.external_ref ?? null,
        },
      };
    case "intake_defect":
      return {
        method: "POST",
        path: `/projects/${ctx.projectId}/defects`,
        body: {
          title: proposal.args.title,
          description: proposal.args.description,
          external_ref: proposal.args.external_ref ?? null,
        },
      };
    case "approval.decide":
      return { notRunnable: "Approvals must be decided in the workspace Decision panel" };
    case "architecture.propose":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/architecture/propose`,
        body: null,
      };
    case "implementation_specs.generate":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/implementation-specs/generate`,
        body: null,
      };
    case "task_plan.generate":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/task-plan/generate`,
        body: null,
      };
    case "change_interpretation.rerun":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/change-interpretation/rerun`,
        body: null,
      };
    case "architecture_delta.propose":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/architecture-delta/propose`,
        body: null,
      };
    case "release.create":
      return {
        method: "POST",
        path: `/delivery-cycles/${ctx.cycleId}/release`,
        body: null,
      };
    default:
      return { notRunnable: `Not runnable from chat: ${proposal.command}` };
  }
}
