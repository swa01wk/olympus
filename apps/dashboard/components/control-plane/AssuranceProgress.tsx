import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import type { Gate } from "@/lib/contracts/entity-types";

export function AssuranceProgress({
  gates,
  assurance,
}: {
  gates: Gate[];
  assurance: Record<string, unknown>;
}) {
  const sentinelFail = assurance.sentinel_fail === true;

  return (
    <Panel title="Assurance Progress" stateRail={sentinelFail ? "failed" : "complete"} actions={<FixtureBadge />}>
      <ul className="space-y-2">
        {gates.map((g) => (
          <li key={g.id} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-mono uppercase">{g.gate_type}</span>
            <StatusBadge value={g.status} />
          </li>
        ))}
        {gates.length === 0 && <p className="text-xs text-[var(--muted)]">No gates for selected IC</p>}
      </ul>
    </Panel>
  );
}
