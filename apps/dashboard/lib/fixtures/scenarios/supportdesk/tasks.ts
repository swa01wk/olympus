import type { Task, TaskContract, TaskDependency } from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

const contract221 = "11111111-1111-4111-8111-111111112001";
const contract222 = "11111111-1111-4111-8111-111111112002";
const contract223 = "11111111-1111-4111-8111-111111112003";

export function buildTasks() {
  const tasks: Task[] = [
    {
      id: IDS.taskForge1,
      delivery_cycle_id: IDS.dc003,
      key: "TASK-221",
      title: "Add priority column to Ticket model",
      work_type: "CODE_CHANGE",
      origin: "IMPLEMENTATION_PLAN",
      status: "RUNNING",
      priority: 100,
      current_contract_id: contract221,
    },
    {
      id: IDS.taskForge2,
      delivery_cycle_id: IDS.dc003,
      key: "TASK-222",
      title: "Expose priority on ticket API",
      work_type: "CODE_CHANGE",
      origin: "IMPLEMENTATION_PLAN",
      status: "RUNNING",
      priority: 90,
      current_contract_id: contract222,
    },
    {
      id: IDS.taskBlocked,
      delivery_cycle_id: IDS.dc003,
      key: "TASK-223",
      title: "Add priority acceptance tests",
      work_type: "CODE_CHANGE",
      origin: "IMPLEMENTATION_PLAN",
      status: "BLOCKED",
      priority: 80,
      blocked_reason: "DEPENDENCY_INCOMPLETE:TASK-222",
      current_contract_id: contract223,
    },
    {
      id: IDS.taskRemediation,
      delivery_cycle_id: IDS.dc003,
      key: "TASK-224",
      title: "Remediate IC-002 merge conflict on ticket routes",
      work_type: "CODE_CHANGE",
      origin: "FINDING",
      status: "COMPLETED",
      priority: 70,
    },
    {
      id: IDS.task301,
      delivery_cycle_id: IDS.dc004,
      key: "TASK-301",
      title: "Return 409 when updating closed ticket",
      work_type: "CODE_CHANGE",
      origin: "DEFECT",
      status: "COMPLETED",
      priority: 100,
    },
  ];

  const contracts: TaskContract[] = [
    {
      id: contract221,
      task_id: IDS.taskForge1,
      key: "TC-221",
      version: 1,
      status: "ISSUED",
      compiled_by: "compiler:1.0",
      content_hash: "abc111",
      body: {
        objective: "Add priority to Ticket",
        work_type: "CODE_CHANGE",
        inputs: [],
        allowed_scope: ["app/models/ticket.py"],
        allowed_actions: ["repo.write", "git.commit", "test.run"],
        required_outputs: ["candidate_commit", "changed_files", "test_results"],
        agent_profile: "forge",
        executor_kind: "AGENT_RUNTIME",
        model_alias: "implementation",
      },
    },
    {
      id: contract222,
      task_id: IDS.taskForge2,
      key: "TC-222",
      version: 1,
      status: "ISSUED",
      compiled_by: "compiler:1.0",
      content_hash: "abc222",
      body: {
        objective: "Expose priority on REST API",
        work_type: "CODE_CHANGE",
        inputs: [],
        allowed_scope: ["app/api/tickets.py", "app/schemas/ticket.py"],
        allowed_actions: ["repo.write", "git.commit", "test.run"],
        required_outputs: ["candidate_commit", "changed_files", "test_results"],
        agent_profile: "forge",
        executor_kind: "AGENT_RUNTIME",
        model_alias: "implementation",
      },
    },
    {
      id: contract223,
      task_id: IDS.taskBlocked,
      key: "TC-223",
      version: 1,
      status: "ISSUED",
      compiled_by: "compiler:1.0",
      content_hash: "abc223",
      body: {
        objective: "Priority acceptance coverage",
        work_type: "VERIFICATION",
        inputs: [],
        allowed_scope: ["tests/acceptance/test_ticket_priority.py"],
        allowed_actions: ["repo.write", "test.run"],
        required_outputs: ["test_results"],
        agent_profile: "forge",
        executor_kind: "AGENT_RUNTIME",
        model_alias: "verification",
      },
    },
  ];

  const dependencies: TaskDependency[] = [
    {
      task_id: IDS.taskBlocked,
      depends_on_task_id: IDS.taskForge2,
      kind: "FINISH_TO_START",
    },
    {
      task_id: IDS.taskForge2,
      depends_on_task_id: IDS.taskForge1,
      kind: "FINISH_TO_START",
    },
  ];

  return { tasks, contracts, dependencies };
}
