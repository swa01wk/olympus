import type {
  BaselineSet,
  BehavioralBaseline,
  ReadinessAssessment,
  RecoveredSpec,
  RepositoryDiscovery,
} from "@/lib/contracts/entity-types";
import { IDS, SHAS } from "./ids";

const now = "2025-09-15T12:00:00.000Z";

export function buildBrownfield() {
  const discovery: RepositoryDiscovery = {
    id: IDS.discovery002,
    delivery_cycle_id: IDS.dc002,
    repository_id: IDS.repo,
    status: "COMPLETE",
    started_at: now,
    finished_at: now,
  };

  const recoveredSpecs: RecoveredSpec[] = [
    {
      id: "11111111-1111-4111-8111-111111112601",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc002,
      key: "RS-FEAT-TICKETS",
      spec_kind: "FEATURE_SPEC",
      title: "Recovered ticket lifecycle",
      knowledge_class: "FACT",
      confidence: 0.92,
      review_status: "PROMOTED",
      promoted_to_spec_id: "11111111-1111-4111-8111-111111112103",
    },
    {
      id: "11111111-1111-4111-8111-111111112602",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc002,
      key: "RS-ROUTE-UPDATE",
      spec_kind: "IMPLEMENTATION_SPEC",
      title: "Ticket update route behavior",
      knowledge_class: "INFERENCE",
      confidence: 0.71,
      review_status: "UNREVIEWED",
    },
    {
      id: "11111111-1111-4111-8111-111111112603",
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc002,
      key: "RS-AUTH-GAP",
      spec_kind: "FEATURE_SPEC",
      title: "Possible SSO hook (unverified)",
      knowledge_class: "UNCERTAINTY",
      confidence: 0.35,
      review_status: "UNREVIEWED",
    },
  ];

  const baselines: BehavioralBaseline[] = Array.from({ length: 12 }, (_, i) => {
    const n = String(i + 1).padStart(3, "0");
    const idSuffix = (0x127000 + i + 1).toString(16).padStart(12, "0");
    return {
      id: `11111111-1111-4111-8111-${idSuffix}`,
      project_id: IDS.project,
      key: `BL-${n}`,
      title: `Behavioral baseline ${n}`,
      repository_sha: SHAS.r1Integrated,
      status: "PASSING",
    };
  });

  const baselineSet: BaselineSet = {
    id: IDS.baselineSetB1,
    project_id: IDS.project,
    key: "B1",
    repository_sha: SHAS.r1Integrated,
    baseline_ids: baselines.map((b) => b.id),
  };

  const readiness: ReadinessAssessment = {
    id: "11111111-1111-4111-8111-111111112801",
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc002,
    state: "READY_FOR_CHANGE",
    assessed_at: now,
    metrics: [
      { name: "recovered_specs_reviewed", value: 1, threshold: 1, ok: true },
      { name: "baselines_passing", value: 12, threshold: 12, ok: true },
      { name: "blocking_uncertainties", value: 0, threshold: 0, ok: true },
    ],
  };

  return { discovery, recoveredSpecs, baselines, baselineSet, readiness };
}
