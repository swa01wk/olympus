import type { Approval, Finding, Gate } from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

const now = "2025-09-15T12:00:00.000Z";

export function buildAssurance() {
  const gates: Gate[] = [
    {
      id: "11111111-1111-4111-8111-111111114001",
      key: "GATE-WARDEN-004",
      delivery_cycle_id: IDS.dc004,
      integration_candidate_id: IDS.ic004,
      gate_type: "WARDEN",
      status: "PASS",
      recommendation: { recommendation: "APPROVE" },
      reasons: [],
      finalized_by: "SYSTEM:gate_finalizer",
      finalized_at: now,
    },
    {
      id: "11111111-1111-4111-8111-111111114002",
      key: "GATE-SENTINEL-004",
      delivery_cycle_id: IDS.dc004,
      integration_candidate_id: IDS.ic004,
      gate_type: "SENTINEL",
      status: "FAIL",
      recommendation: { recommended: "FAIL", uncovered_obligations: ["AC-004-02"] },
      reasons: ["OBLIGATION_FAILED:AC-004-02"],
      finalized_by: "SYSTEM:gate_finalizer",
      finalized_at: now,
    },
  ];

  const findings: Finding[] = [
    {
      id: "11111111-1111-4111-8111-111111115001",
      key: "FND-042",
      delivery_cycle_id: IDS.dc004,
      integration_candidate_id: IDS.ic004,
      source: "SENTINEL",
      category: "CORRECTNESS",
      severity: "BLOCKER",
      blocking: true,
      title: "AC-004-02 missing executable evidence",
      status: "OPEN",
    },
    {
      id: IDS.fndIc002Conflict,
      key: "FND-IC2-001",
      delivery_cycle_id: IDS.dc003,
      integration_candidate_id: IDS.ic002,
      source: "INTEGRATION",
      category: "CONFLICT",
      severity: "BLOCKER",
      blocking: true,
      title: "IC-002 merge conflict on ticket routes",
      status: "RESOLVED",
    },
  ];

  const approvals: Approval[] = [
    {
      id: IDS.approvalReleaseR3,
      key: "APR-221",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc004,
      approval_type: "RELEASE",
      subject_type: "release_manifest",
      subject_id: IDS.r3,
      subject_version: 1,
      subject_hash: "manifest-hash-r3",
      status: "PENDING",
    },
    {
      id: IDS.approvalAction,
      key: "APR-903",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc003,
      approval_type: "ACTION",
      subject_type: "action_request",
      subject_id: "11111111-1111-4111-8111-111111119003",
      status: "PENDING",
    },
  ];

  return { gates, findings, approvals };
}
