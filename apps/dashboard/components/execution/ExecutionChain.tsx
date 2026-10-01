import Link from "next/link";
import type { Execution, Task, TaskContract } from "@/lib/contracts/entity-types";

export function ExecutionChain({
  task,
  contract,
  execution,
}: {
  task?: Task;
  contract?: TaskContract;
  execution: Execution;
}) {
  const steps = [
    { label: "Task", value: task?.key, href: task ? undefined : undefined },
    { label: "TaskContract", value: contract ? `${contract.key}:v${contract.version}` : "—" },
    { label: "Eligibility", value: "server" },
    { label: "Execution", value: execution.key, href: `/executions/${execution.id}` },
    { label: "Snapshot", value: execution.snapshot_id ? execution.snapshot_id.slice(0, 8) : "—" },
    { label: "Lease", value: "ACTIVE when leased" },
    { label: "Worktree", value: "writable" },
    { label: "AgentRuntime", value: execution.agent_profile ?? "—" },
    { label: "ToolGateway", value: "actions" },
    { label: "Candidate Commit", value: "when produced" },
  ];

  return (
    <ol className="flex flex-wrap items-center gap-2 text-[11px]">
      {steps.map((s, i) => (
        <li key={s.label} className="flex items-center gap-2">
          {i > 0 && <span className="text-[var(--muted)]">→</span>}
          <span className="rounded border border-[var(--border)] bg-[var(--raised)] px-2 py-1">
            <span className="text-[var(--muted)]">{s.label}: </span>
            {s.href ? (
              <Link href={s.href} className="font-mono text-sky-300 hover:underline">
                {s.value}
              </Link>
            ) : (
              <span className="font-mono">{s.value ?? "—"}</span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}
