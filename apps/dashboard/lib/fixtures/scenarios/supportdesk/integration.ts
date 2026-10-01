import type {
  DeliveryCycle,
  IntegrationCandidate,
  Project,
  Release,
  ReleaseEligibilityEvaluation,
} from "@/lib/contracts/entity-types";
import { IDS, SHAS } from "./ids";

export function buildIntegrationCore() {
  const project: Project = {
    id: IDS.project,
    key: "SUPPORTDESK",
    name: "SupportDesk",
    description: "Ticket management reference application",
    readiness_state: "READY_FOR_CHANGE",
    active_baseline_set_id: IDS.baselineSetB1,
  };

  const cycles: DeliveryCycle[] = [
    {
      id: IDS.dc001,
      project_id: IDS.project,
      key: "DC-001",
      type: "GREENFIELD_BUILD",
      objective: "Initial SupportDesk R1",
      state: "COMPLETE",
      state_version: 12,
      repository_id: IDS.repo,
    },
    {
      id: IDS.dc002,
      project_id: IDS.project,
      key: "DC-002",
      type: "BROWNFIELD_ONBOARDING",
      objective: "Onboard R1 repository",
      state: "READY",
      state_version: 8,
      repository_id: IDS.repo,
    },
    {
      id: IDS.dc003,
      project_id: IDS.project,
      key: "DC-003",
      type: "FEATURE_CHANGE",
      objective: "Add Ticket Priority",
      state: "DEVELOPMENT",
      state_version: 5,
      repository_id: IDS.repo,
      base_sha: SHAS.dc003Base,
    },
    {
      id: IDS.dc004,
      project_id: IDS.project,
      key: "DC-004",
      type: "BUG_FIX",
      objective: "Closed ticket update returns HTTP 500",
      state: "ASSURANCE",
      state_version: 9,
      repository_id: IDS.repo,
      base_sha: SHAS.dc004Base,
    },
  ];

  const ics: IntegrationCandidate[] = [
    {
      id: IDS.ic001,
      key: "IC-001",
      delivery_cycle_id: IDS.dc001,
      repository_id: IDS.repo,
      base_sha: SHAS.r1Integrated,
      integrated_sha: SHAS.r1Integrated,
      status: "READY",
      ordering: [],
      canonical_index_version_id: IDS.idxCanonicalR1,
    },
    {
      id: IDS.ic002,
      key: "IC-002",
      delivery_cycle_id: IDS.dc003,
      repository_id: IDS.repo,
      base_sha: SHAS.dc003Base,
      integrated_sha: null,
      status: "SUPERSEDED",
      ordering: [
        {
          task_key: "TASK-221",
          candidate_commit_sha: SHAS.candidate551,
          position: 0,
          reason: "Superseded after CONFLICT finding FND-IC2-001",
        },
      ],
    },
    {
      id: IDS.ic003,
      key: "IC-003",
      delivery_cycle_id: IDS.dc003,
      repository_id: IDS.repo,
      base_sha: SHAS.dc003Base,
      integrated_sha: null,
      status: "CREATED",
      ordering: [],
    },
    {
      id: IDS.ic004,
      key: "IC-004",
      delivery_cycle_id: IDS.dc004,
      repository_id: IDS.repo,
      base_sha: SHAS.dc004Base,
      integrated_sha: SHAS.dc004Integrated,
      status: "READY",
      ordering: [
        {
          task_key: "TASK-301",
          candidate_commit_sha: SHAS.candidate301,
          position: 0,
        },
      ],
      canonical_index_version_id: IDS.idxCanonicalIc004,
    },
  ];

  const releases: Release[] = [
    {
      id: IDS.r1,
      key: "R1",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc001,
      integration_candidate_id: IDS.ic001,
      integrated_sha: SHAS.r1Integrated,
      status: "RELEASED",
    },
    {
      id: IDS.r2,
      key: "R2",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc003,
      integration_candidate_id: IDS.ic003,
      integrated_sha: SHAS.dc003Draft,
      status: "DRAFT",
    },
    {
      id: IDS.r3,
      key: "R3",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc004,
      integration_candidate_id: IDS.ic004,
      integrated_sha: SHAS.dc004Integrated,
      status: "NOT_ELIGIBLE",
    },
  ];

  const eligibilityByCycle: ReleaseEligibilityEvaluation[] = [
    {
      delivery_cycle_id: IDS.dc001,
      integration_candidate_id: IDS.ic001,
      eligible: true,
      conditions: [{ name: "manifest_valid", ok: true, reasons: [] }],
    },
    {
      delivery_cycle_id: IDS.dc004,
      integration_candidate_id: IDS.ic004,
      eligible: false,
      conditions: [
        { name: "required_gates_pass", ok: false, reasons: ["Sentinel Gate failed"] },
        { name: "blocking_findings", ok: false, reasons: ["Blocking Finding FND-042"] },
        {
          name: "mandatory_acceptance_criteria_have_evidence",
          ok: false,
          reasons: ["AC-004-02 missing evidence"],
        },
        { name: "manifest_valid", ok: true, reasons: [] },
      ],
    },
  ];

  return { project, cycles, ics, releases, eligibilityByCycle };
}
