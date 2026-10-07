import type { WhyView } from "@/components/inspector/WhyPanel";
import type { CommandPreview } from "@/components/inspector/CommandList";
import type { AllowedCommand, TransitionPreview } from "@/src/api/types/core";
import type { ControlPlaneGraphNode } from "@/src/control-plane/graph-types";

export function whyForNode(
  node: ControlPlaneGraphNode,
  ctx: {
    cycleTransitions?: TransitionPreview[];
    taskBlockedReason?: string | null;
  },
): WhyView | undefined {
  if (node.kind === "Task") {
    if (node.sub || ctx.taskBlockedReason) {
      return {
        summary: node.sub ?? ctx.taskBlockedReason ?? "Task is blocked.",
        checks: [["Scheduler eligibility", node.status === "blocked" ? false : true, node.sub]],
        next: "Resolve blocking predicates or complete dependencies.",
      };
    }
    return {
      summary: `Task is ${node.backendStatus ?? node.status}.`,
      next: "Open Task DAG for scheduler predicates and contract.",
    };
  }

  if (node.kind === "Execution") {
    return {
      summary: `Execution attempt is ${node.backendStatus ?? node.status}.`,
      next: "Open Execution Inspector for tool gateway events and snapshot boundary.",
    };
  }

  return {
    summary: `${node.kind} is ${node.backendStatus ?? node.status}.`,
  };
}

export function commandsForCycle(
  allowed: AllowedCommand[],
  expectedState: string,
): CommandPreview[] {
  return allowed.map((c) => ({
    label: c.command.replace(/_/g, " "),
    cmd: `POST …/commands/${c.command} · expected_state=${expectedState}`,
    enabled: c.allowed,
    reason: c.guard_preview.length ? c.guard_preview.join("; ") : undefined,
    cycleCommand: { command: c.command, expectedState },
  }));
}

export function whyForCycleState(
  state: string,
  transitions: TransitionPreview[],
): WhyView {
  const blocked = transitions.filter((t) => !t.allowed);
  return {
    summary: `Delivery cycle is in ${state}.`,
    checks: blocked.flatMap((t) =>
      t.guard_results
        .filter((g) => !g.ok)
        .map((g) => [g.guard_id, false as const, g.reasons.join(", ")] as [string, false, string]),
    ),
    next: blocked[0]?.command
      ? `Next transition: ${blocked[0].command} (${blocked[0].guard_preview.join("; ") || "ready"})`
      : "Transitions may proceed when guards pass.",
  };
}
