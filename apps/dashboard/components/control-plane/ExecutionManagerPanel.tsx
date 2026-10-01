import Link from "next/link";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import type { Execution } from "@/lib/contracts/entity-types";
import { isExecutionActive } from "@/lib/utils/execution-active";

export function ExecutionManagerPanel({ executions, manager }: { executions: Execution[]; manager: Record<string, unknown> }) {
  const active = executions.filter((e) => isExecutionActive(e.status));
  const serverRunning = Number(manager.running ?? active.length);

  return (
    <Panel title="Execution Manager" stateRail={active.length ? "running" : "neutral"} actions={<FixtureBadge />}>
      <p className="mb-2 text-xs text-[var(--muted)]">Running (server): {serverRunning}</p>
      <ul className="space-y-2">
        {active.map((e) => (
          <li key={e.id}>
            <Link href={`/executions/${e.id}`} className="flex flex-wrap items-center gap-2 text-sm hover:underline">
              <span className="font-mono text-sky-300">{e.key}</span>
              <StatusBadge value={e.status} kind="execution" />
              <span className="text-[var(--muted)]">{e.agent_profile}</span>
            </Link>
          </li>
        ))}
        {active.length === 0 && <p className="text-xs text-[var(--muted)]">No active executions</p>}
      </ul>
    </Panel>
  );
}
