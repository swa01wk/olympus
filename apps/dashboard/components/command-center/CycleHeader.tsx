import Link from "next/link";
import { StatusBadge } from "@/components/status/StatusBadge";
import type { DeliveryCycle, Project } from "@/lib/contracts/entity-types";

export function CycleHeader({
  project,
  cycle,
  projectId,
  targetReleaseKey,
}: {
  project: Project;
  cycle: DeliveryCycle;
  projectId: string;
  targetReleaseKey?: string | null;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold">Command Center</h1>
        <p className="text-[var(--muted)]">
          <span className="font-mono text-amber-300">{project.key}</span> — {project.name}
        </p>
        <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs md:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-[var(--muted)]">Cycle</dt>
            <dd className="font-mono">{cycle.key}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Journey</dt>
            <dd>{cycle.type}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Stage</dt>
            <dd>
              <StatusBadge value={cycle.state} preferred="running" />
            </dd>
          </div>
          <div className="md:col-span-2">
            <dt className="text-[var(--muted)]">Objective</dt>
            <dd>{cycle.objective}</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Risk</dt>
            <dd>Not available (M-13)</dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Target release</dt>
            <dd className="font-mono">{targetReleaseKey ?? "—"}</dd>
          </div>
        </dl>
      </div>
      <Link
        href={`/projects/${projectId}/cycles/${cycle.id}?cycle=${cycle.id}`}
        className="text-xs text-amber-400 underline"
      >
        Cycle Forge
      </Link>
    </header>
  );
}
