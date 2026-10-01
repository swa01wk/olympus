import type {
  CandidateCommit,
  Execution,
  ExecutionSnapshot,
  Worktree,
} from "@/lib/contracts/entity-types";
import { IDS } from "./ids";
import { SHAS } from "./ids";

const now = "2025-09-15T12:00:00.000Z";
const earlier = "2025-09-15T11:00:00.000Z";

export function buildExecutions() {
  const executions: Execution[] = [
    {
      id: IDS.ex548,
      key: "EX-548",
      task_id: IDS.taskForge1,
      delivery_cycle_id: IDS.dc003,
      attempt_number: 1,
      status: "FAILED",
      executor_kind: "AGENT_RUNTIME",
      agent_profile: "forge",
      failure_class: "TEST_FAILURE",
      started_at: earlier,
      finished_at: now,
    },
    {
      id: IDS.ex551,
      key: "EX-551",
      task_id: IDS.taskForge1,
      delivery_cycle_id: IDS.dc003,
      attempt_number: 2,
      status: "STARTED",
      executor_kind: "AGENT_RUNTIME",
      agent_profile: "forge",
      previous_execution_id: IDS.ex548,
      started_at: now,
    },
    {
      id: IDS.ex552,
      key: "EX-552",
      task_id: IDS.taskForge2,
      delivery_cycle_id: IDS.dc003,
      attempt_number: 1,
      status: "STARTED",
      executor_kind: "AGENT_RUNTIME",
      agent_profile: "forge",
      started_at: now,
    },
    {
      id: IDS.ex301,
      key: "EX-301",
      task_id: IDS.task301,
      delivery_cycle_id: IDS.dc004,
      attempt_number: 1,
      status: "COMPLETED",
      executor_kind: "AGENT_RUNTIME",
      agent_profile: "forge",
      started_at: earlier,
      finished_at: now,
    },
  ];

  const snapshots: ExecutionSnapshot[] = [
    {
      id: "11111111-1111-4111-8111-111111118001",
      execution_id: IDS.ex551,
      task_contract_hash: "abc111",
      base_commit: SHAS.dc003Base,
      snapshot_hash: "snap-ex551",
      content: { worktree: "wt-ex551", model_alias: "implementation" },
    },
    {
      id: "11111111-1111-4111-8111-111111118002",
      execution_id: IDS.ex552,
      task_contract_hash: "abc222",
      base_commit: SHAS.dc003Base,
      snapshot_hash: "snap-ex552",
      content: { worktree: "wt-ex552", model_alias: "implementation" },
    },
  ];

  const worktrees: Worktree[] = [
    {
      execution_id: IDS.ex551,
      path: "/var/olympus/worktrees/ex-551",
      branch: "forge/task-221",
      base_sha: SHAS.dc003Base,
      mode: "ISOLATED",
      status: "ACTIVE",
    },
    {
      execution_id: IDS.ex552,
      path: "/var/olympus/worktrees/ex-552",
      branch: "forge/task-222",
      base_sha: SHAS.dc003Base,
      mode: "ISOLATED",
      status: "ACTIVE",
    },
  ];

  const candidateCommits: CandidateCommit[] = [
    {
      sha: SHAS.candidate551,
      parent_sha: SHAS.dc003Base,
      base_sha: SHAS.dc003Base,
      execution_id: IDS.ex551,
      changed_files: [
        { path: "app/models/ticket.py", change_type: "MODIFIED", additions: 12, deletions: 1 },
      ],
    },
    {
      sha: SHAS.candidate552,
      parent_sha: SHAS.dc003Base,
      base_sha: SHAS.dc003Base,
      execution_id: IDS.ex552,
      changed_files: [
        { path: "app/api/tickets.py", change_type: "MODIFIED", additions: 8, deletions: 0 },
      ],
    },
  ];

  return { executions, snapshots, worktrees, candidateCommits };
}
