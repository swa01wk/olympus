import type { ScenarioCheckpointMeta, ScenarioId } from "@/lib/api/scenario-controller";

export interface CheckpointDef extends ScenarioCheckpointMeta {
  apply?: string;
  advancesOn?: { approval_key?: string; command?: string };
}

function cp(
  index: number,
  id: string,
  label: string,
  narrative: string,
  lookAt: string[],
  advancesOn?: CheckpointDef["advancesOn"],
): CheckpointDef {
  return { index, id, label, narrative, lookAt, advancesOn };
}

const greenfieldCheckpoints: CheckpointDef[] = [
  cp(0, "00-intake", "Intake", "Project + PRD PS-001", ["Command Center", "Product"]),
  cp(1, "01-product-model", "Product model", "Capabilities, features, FeatureSpecs", ["Product tree"]),
  cp(2, "02-scope-approval", "Scope approval", "APR-001 SCOPE PENDING", ["Inbox", "Product"], {
    approval_key: "APR-001",
  }),
  cp(3, "03-repository-provisioned", "Repository provisioned", "REPO READY gf-init-001", [
    "Repository",
    "Commits",
  ]),
  cp(4, "04-architecture", "Architecture", "ARCH-001 approved", ["Product architecture"]),
  cp(5, "05-implementation-specs", "Implementation specs", "IS-101..110", ["Product specs"]),
  cp(6, "06-task-plan", "Task plan", "TASK-101..124 DAG", ["Task DAG", "Control Plane"]),
  cp(7, "07-development-started", "Development started", "EX-111..114", ["Command Center", "Workspaces"]),
  cp(8, "08-development-running", "Development running", "EX-112 fail, EX-115 retry, actions", [
    "Execution",
    "Actions",
  ]),
  cp(9, "09-candidate-commits", "Candidate commits", "14 candidates", ["Commits", "Workspaces"]),
  cp(10, "10-integration", "Integration", "IC-001 integrating", ["Integration Forge"]),
  cp(11, "11-canonical-reindex", "Canonical re-index", "CODEIDX-R1 @ 73fb91d", ["Code graph", "Lineage"]),
  cp(12, "12-assurance", "Assurance", "Warden + Sentinel PASS", ["Assurance", "Evidence"]),
  cp(13, "13-release-ready", "Release ready", "R1 ELIGIBLE APR-004", ["Release", "Inbox"], {
    approval_key: "APR-004",
  }),
  cp(14, "14-released", "Released R1", "Greenfield R1 complete", ["Release", "Repository", "Audit"]),
];

const brownfieldCheckpoints: CheckpointDef[] = [
  cp(0, "00-registration", "Registration", "EXTERNAL_CLONE registered", ["Repository", "Brownfield"]),
  cp(1, "01-credential-resolution", "Credential", "Authentication CONNECTED", ["Repository pipeline"]),
  cp(2, "02-cloning", "Cloning", "Clone in progress", ["Repository pipeline"]),
  cp(3, "03-validating", "Validating", "Verify repository", ["Repository pipeline"]),
  cp(4, "04-head-resolved", "Head resolved", "main → 73fb91d", ["Repository header"]),
  cp(5, "05-workspace-ready", "Workspace ready", "WS-001 READY", ["Workspaces", "Commits"]),
  cp(6, "06-code-index", "Code index", "CODEIDX-R1 BUILDING→READY", ["Code graph"]),
  cp(7, "07-discovery", "Discovery", "Routes, tests, discovery", ["Brownfield facts"]),
  cp(8, "08-recovered-specs", "Recovered specs", "FACT/INFERENCE/UNCERTAINTY", ["Recovered specs"]),
  cp(9, "09-baselines", "Baselines", "BL-001..010", ["Baselines"]),
  cp(10, "10-human-review", "Human review", "Promotion queue APR-010", ["Inbox", "Review"], {
    approval_key: "APR-010",
  }),
  cp(11, "11-ready-for-change", "Ready for change", "READY_FOR_CHANGE B1", ["Readiness", "Command Center"]),
];

const featureChangeCheckpoints: CheckpointDef[] = [
  cp(0, "00-intake", "Intake", "CR-003 change request", ["Change request"]),
  cp(1, "01-spec-delta", "Spec delta", "FS-001 v1→v2 priority", ["Product deltas"]),
  cp(2, "02-impact", "Impact", "IA-003 direct/transitive", ["Impact explorer"]),
  cp(3, "03-planning", "Planning", "TASK-221..227", ["Task DAG"]),
  cp(4, "04-development-started", "Development started", "EX-548/552/553", ["Command Center"]),
  cp(5, "05-development-running", "Development running", "EX-551 retry, actions denied", [
    "Command Center",
    "Executions",
    "Control Plane",
  ]),
  cp(6, "06-candidate-commits", "Candidate commits", "aaa5511..ddd5544", ["Commits", "Workspaces"]),
  cp(7, "07-integration", "Integration", "IC-003 integrating", ["Integration Forge"]),
  cp(8, "08-canonical-reindex", "Canonical re-index", "CODEIDX-R2 @ r2-def456", ["Repository", "Index history"]),
  cp(9, "09-assurance", "Assurance", "Gates PASS at r2", ["Assurance", "Evidence"]),
  cp(10, "10-release-ready", "Release ready", "R2 ELIGIBLE", ["Release", "Inbox"], { approval_key: "APR-R2" }),
  cp(11, "11-released", "R2 released", "Feature change complete", ["Release R2", "Repository"]),
];

const bugFixCheckpoints: CheckpointDef[] = [
  cp(0, "00-defect-intake", "Defect intake", "DEF-004", ["Defect"]),
  cp(1, "01-reproduction", "Reproduction", "EV-REP-001 FAIL HTTP 500", ["Defect", "Evidence"]),
  cp(2, "02-expected-behavior", "Expected behavior", "UNKNOWN → 409", ["Inbox", "Defect"], {
    approval_key: "APR-EB-004",
  }),
  cp(3, "03-root-cause", "Root cause", "TraceCorrelation path", ["Defect code path"]),
  cp(4, "04-repair-spec", "Repair spec", "REG-004 + TASK-302", ["Task DAG"]),
  cp(5, "05-repair-execution", "Repair execution", "EX-602 candidate 5e1f0aa", ["Execution"]),
  cp(6, "06-integration", "Integration", "IC-004 → 982af11", ["Integration Forge"]),
  cp(7, "07-assurance-fail", "Assurance fail", "FND-042, R3 blocked", ["Assurance", "Release"]),
  cp(8, "08-remediation", "Remediation", "TASK-303 EX-603", ["Task DAG", "Execution"]),
  cp(9, "09-reintegration", "Reintegration", "IC-005 supersedes IC-004", ["Integration Forge"]),
  cp(10, "10-assurance-pass", "Assurance pass", "R3 ELIGIBLE", ["Assurance", "Release"], {
    approval_key: "APR-221",
  }),
  cp(11, "11-released", "R3 released", "Remediation + R3", ["Release R3", "Defect"]),
];

export const SCENARIO_CHECKPOINTS: Record<ScenarioId, CheckpointDef[]> = {
  greenfield: greenfieldCheckpoints,
  brownfield: brownfieldCheckpoints,
  "feature-change": featureChangeCheckpoints,
  "bug-fix": bugFixCheckpoints,
};

export { DEFAULT_SCENARIO, DEFAULT_CHECKPOINT_ID } from "@/lib/api/fx-param";
