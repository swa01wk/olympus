import Link from "next/link";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import type { IntegrationCandidate } from "@/lib/contracts/entity-types";

export function IcForge({
  ic,
  projectId,
  cycleId,
}: {
  ic: IntegrationCandidate;
  projectId: string;
  cycleId: string;
}) {
  const chain = [
    { label: "Tasks", href: `/projects/${projectId}/cycles/${cycleId}/tasks?cycle=${cycleId}` },
    { label: "Executions", href: `/projects/${projectId}/executions?cycle=${cycleId}` },
    { label: "IC", value: ic.key },
    { label: "integrated_sha", value: ic.integrated_sha?.slice(0, 12) },
    { label: "Assurance", href: `/projects/${projectId}/assurance?ic=${ic.id}&cycle=${cycleId}` },
  ];

  return (
    <div className="space-y-4">
      <header className="flex items-center gap-2">
        <h2 className="font-mono text-lg text-amber-300">{ic.key}</h2>
        <StatusBadge value={ic.status} />
        <FixtureBadge />
      </header>
      <Panel title="Convergence chain" stateRail="running" actions={<FixtureBadge />}>
        <ol className="flex flex-wrap gap-2 text-xs">
          {chain.map((s) => (
            <li key={s.label} className="rounded border border-[var(--border)] px-2 py-1">
              {s.href ? (
                <Link href={s.href} className="text-sky-300 underline">
                  {s.label}
                </Link>
              ) : (
                <>
                  <span className="text-[var(--muted)]">{s.label}: </span>
                  <span className="font-mono">{s.value}</span>
                </>
              )}
            </li>
          ))}
        </ol>
      </Panel>
    </div>
  );
}
