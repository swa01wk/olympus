import type { DomainEvent } from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

const t0 = Date.parse("2025-09-01T10:00:00.000Z");

function at(offsetMinutes: number) {
  return new Date(t0 + offsetMinutes * 60_000).toISOString();
}

const EVENT_SPECS: Array<Omit<DomainEvent, "id" | "sequence">> = [
  {
    event_type: "delivery_cycle.completed",
    aggregate_type: "delivery_cycle",
    aggregate_id: IDS.dc001,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc001,
    payload: { key: "DC-001" },
    correlation_id: "corr-dc001-complete",
    occurred_at: at(10),
  },
  {
    event_type: "integration_candidate.ready",
    aggregate_type: "integration_candidate",
    aggregate_id: IDS.ic001,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc001,
    payload: { key: "IC-001", integrated_sha: "aaa111…" },
    correlation_id: "corr-ic001",
    occurred_at: at(12),
  },
  {
    event_type: "release.released",
    aggregate_type: "release",
    aggregate_id: IDS.r1,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc001,
    payload: { key: "R1" },
    correlation_id: "corr-r1",
    occurred_at: at(15),
  },
  {
    event_type: "brownfield.readiness.assessed",
    aggregate_type: "readiness_assessment",
    aggregate_id: "11111111-1111-4111-8111-111111112801",
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc002,
    payload: { state: "READY_FOR_CHANGE" },
    correlation_id: "corr-dc002-ready",
    occurred_at: at(120),
  },
  {
    event_type: "change_request.ingested",
    aggregate_type: "change_request",
    aggregate_id: IDS.cr003,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { key: "CR-003" },
    correlation_id: "corr-cr003",
    occurred_at: at(200),
  },
  {
    event_type: "execution.started",
    aggregate_type: "execution",
    aggregate_id: IDS.ex548,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { execution_key: "EX-548" },
    correlation_id: "corr-ex548",
    occurred_at: at(210),
  },
  {
    event_type: "execution.failed",
    aggregate_type: "execution",
    aggregate_id: IDS.ex548,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { failure_class: "TEST_FAILURE" },
    correlation_id: "corr-ex548",
    occurred_at: at(215),
  },
  {
    event_type: "execution.created",
    aggregate_type: "execution",
    aggregate_id: IDS.ex551,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { execution_key: "EX-551", previous: "EX-548" },
    correlation_id: "corr-ex551",
    occurred_at: at(216),
  },
  {
    event_type: "execution.started",
    aggregate_type: "execution",
    aggregate_id: IDS.ex551,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { execution_key: "EX-551", agent_profile: "forge" },
    correlation_id: "corr-ex551",
    occurred_at: at(217),
  },
  {
    event_type: "execution.started",
    aggregate_type: "execution",
    aggregate_id: IDS.ex552,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { execution_key: "EX-552", agent_profile: "forge" },
    correlation_id: "corr-ex552",
    occurred_at: at(218),
  },
  {
    event_type: "action.requested",
    aggregate_type: "action_request",
    aggregate_id: "11111111-1111-4111-8111-111111119001",
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { tool: "repo", action: "write" },
    correlation_id: "corr-act-901",
    occurred_at: at(219),
  },
  {
    event_type: "action.denied",
    aggregate_type: "action_request",
    aggregate_id: "11111111-1111-4111-8111-111111119002",
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { reason: "forge.no_direct_main_push" },
    correlation_id: "corr-act-902",
    occurred_at: at(220),
  },
  {
    event_type: "integration_candidate.conflict",
    aggregate_type: "integration_candidate",
    aggregate_id: IDS.ic002,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { key: "IC-002", finding: "FND-IC2-001" },
    correlation_id: "corr-ic002",
    occurred_at: at(180),
  },
  {
    event_type: "integration_candidate.superseded",
    aggregate_type: "integration_candidate",
    aggregate_id: IDS.ic002,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc003,
    payload: { superseded_by: "IC-003" },
    correlation_id: "corr-ic002",
    occurred_at: at(190),
  },
  {
    event_type: "defect.triaged",
    aggregate_type: "defect",
    aggregate_id: IDS.defect004,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc004,
    payload: { key: "DEF-004" },
    correlation_id: "corr-def004",
    occurred_at: at(300),
  },
  {
    event_type: "gate.finalized",
    aggregate_type: "gate",
    aggregate_id: "11111111-1111-4111-8111-111111114001",
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc004,
    payload: { gate_type: "WARDEN", status: "PASS" },
    correlation_id: "corr-gates-004",
    occurred_at: at(320),
  },
  {
    event_type: "gate.finalized",
    aggregate_type: "gate",
    aggregate_id: "11111111-1111-4111-8111-111111114002",
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc004,
    payload: { gate_type: "SENTINEL", status: "FAIL" },
    correlation_id: "corr-gates-004",
    occurred_at: at(321),
  },
  {
    event_type: "finding.created",
    aggregate_type: "finding",
    aggregate_id: "11111111-1111-4111-8111-111111115001",
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc004,
    payload: { key: "FND-042", blocking: true },
    correlation_id: "corr-fnd042",
    occurred_at: at(322),
  },
  {
    event_type: "approval.requested",
    aggregate_type: "approval",
    aggregate_id: IDS.approvalReleaseR3,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc004,
    payload: { key: "APR-221", approval_type: "RELEASE" },
    correlation_id: "corr-apr221",
    occurred_at: at(325),
  },
];

const EXTRA_TEMPLATES = [
  "task.ready",
  "task.blocked",
  "candidate_commit.created",
  "code_index.built",
  "model_call.completed",
  "checkpoint.saved",
  "worktree.created",
] as const;

export function buildEvents() {
  const events: DomainEvent[] = EVENT_SPECS.map((spec, i) => ({
    id: `11111111-1111-4111-8111-${(0x116000 + i + 1).toString(16).padStart(12, "0")}`,
    sequence: i + 1,
    ...spec,
  }));

  let seq = events.length;
  let minute = 400;
  for (let cycleIdx = 0; cycleIdx < 4; cycleIdx += 1) {
    const cycleId = [IDS.dc001, IDS.dc002, IDS.dc003, IDS.dc004][cycleIdx]!;
    for (const template of EXTRA_TEMPLATES) {
      seq += 1;
      minute += 1;
      events.push({
        id: `11111111-1111-4111-8111-${(0x116000 + seq).toString(16).padStart(12, "0")}`,
        sequence: seq,
        event_type: template,
        aggregate_type: "delivery_cycle",
        aggregate_id: cycleId,
        project_id: IDS.project,
        delivery_cycle_id: cycleId,
        payload: { template, cycle: `DC-00${cycleIdx + 1}` },
        correlation_id: `corr-extra-${cycleIdx}-${template}`,
        occurred_at: at(minute),
      });
    }
  }

  return { events };
}
