"use client";

import type { ControlDecision } from "@/lib/contracts/entity-types";
import { Panel } from "@/components/design/Panel";

const QUESTION_LABELS: Record<ControlDecision["question_kind"], string> = {
  TASK_BLOCKED: "Why is this task blocked?",
  INTEGRATION_UNAVAILABLE: "Why is integration unavailable?",
  ACTION_DENIED: "Why was this action denied?",
  GATE_FAILED: "Why did this gate fail?",
  RELEASE_BLOCKED: "Why is release blocked?",
};

export function DecisionExplainer({ decision }: { decision: ControlDecision | null }) {
  if (!decision) {
    return (
      <Panel title="Decision explainer" stateRail="neutral">
        <p className="text-xs text-[var(--muted)]">No explanation record for this subject.</p>
      </Panel>
    );
  }

  return (
    <Panel title={QUESTION_LABELS[decision.question_kind]} stateRail="neutral">
      <p className="text-sm font-medium">{decision.outcome}</p>
      <ul className="mt-2 space-y-1 text-xs">
        {decision.conditions.map((c) => (
          <li key={c.name} className={c.ok ? "text-emerald-300" : "text-rose-300"}>
            {c.ok ? "✓" : "✗"} {c.name}: {c.detail}
          </li>
        ))}
      </ul>
      <p className="mt-2 font-mono text-[10px] text-[var(--muted)]">{decision.source_endpoint}</p>
    </Panel>
  );
}
