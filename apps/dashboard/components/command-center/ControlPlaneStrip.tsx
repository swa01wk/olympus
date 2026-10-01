import Link from "next/link";
import type { ControlPlaneView } from "@/lib/contracts/entity-types";

export function ControlPlaneStrip({
  projectId,
  cycleId,
  view,
}: {
  projectId: string;
  cycleId: string;
  view: ControlPlaneView;
}) {
  const chips = [
    { label: "Scheduler", value: String(view.scheduler.queued_tasks ?? "—") },
    { label: "Running", value: String(view.execution_manager.running ?? "—") },
    { label: "Denied actions", value: String(view.policy.denied_actions ?? "—") },
    { label: "IC", value: String(view.integration.active_ic ?? "—") },
    {
      label: "Release",
      value: view.release.eligible == null ? "n/a" : view.release.eligible ? "eligible" : "blocked",
    },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--raised)] px-3 py-2 text-xs">
      <span className="font-semibold uppercase text-[var(--muted)]">Control plane</span>
      {chips.map((c) => (
        <span key={c.label} className="rounded border border-[var(--border)] px-2 py-0.5">
          {c.label}: <strong className="font-mono">{c.value}</strong>
        </span>
      ))}
      <Link
        href={`/projects/${projectId}/control-plane?cycle=${cycleId}`}
        className="ml-auto text-amber-400 underline"
      >
        Inspect
      </Link>
    </div>
  );
}
