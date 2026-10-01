import Link from "next/link";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import type { IntegrationCandidate } from "@/lib/contracts/entity-types";

export function IntegrationReadiness({
  projectId,
  cycleId,
  ics,
  integration,
}: {
  projectId: string;
  cycleId: string;
  ics: IntegrationCandidate[];
  integration: Record<string, unknown>;
}) {
  const activeKey = integration.active_ic as string | undefined;
  const current = ics.filter((ic) => ic.status !== "SUPERSEDED");

  return (
    <Panel title="Integration Readiness" stateRail="waiting" actions={<FixtureBadge />}>
      {activeKey && <p className="mb-2 text-xs">Active IC (server): {activeKey}</p>}
      <ul className="space-y-2">
        {current.map((ic) => (
          <li key={ic.id}>
            <Link
              href={`/projects/${projectId}/cycles/${cycleId}/integration?ic=${ic.id}&cycle=${cycleId}`}
              className="flex flex-wrap items-center gap-2 hover:underline"
            >
              <span className="font-mono text-amber-300">{ic.key}</span>
              <StatusBadge value={ic.status} />
              <span className="font-mono text-[10px] text-[var(--muted)]">{ic.integrated_sha?.slice(0, 12)}…</span>
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
