import { Panel } from "@/components/design/Panel";
import type { ActionRequest } from "@/lib/contracts/entity-types";

const STEPS = [
  "schema_validation",
  "policy_evaluation",
  "approval_gate",
  "lease_check",
  "worktree_scope",
  "tool_allowlist",
  "rate_limit",
  "audit_emit",
] as const;

export function ActionGovernancePipeline({ action }: { action?: ActionRequest }) {
  const failing =
    action?.status === "DENIED"
      ? "policy_evaluation"
      : action?.status === "PENDING_APPROVAL"
        ? "approval_gate"
        : null;

  return (
    <Panel title="Action governance pipeline (Phase 04)" stateRail={failing ? "blocked" : "complete"}>
      <ol className="space-y-1 text-xs">
        {STEPS.map((s) => (
          <li
            key={s}
            className={`rounded px-2 py-1 font-mono ${s === failing ? "bg-rose-950/40 text-rose-200" : "text-[var(--muted)]"}`}
          >
            {s === failing ? "✕" : "·"} {s}
          </li>
        ))}
      </ol>
    </Panel>
  );
}
