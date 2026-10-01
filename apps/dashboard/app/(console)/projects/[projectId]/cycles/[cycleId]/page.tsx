"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { LifecycleForge } from "@/components/lifecycle/LifecycleForge";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import { buildForgeStages } from "@/lib/view-models/lifecycle";

export default function CycleForgePage() {
  const { projectId, cycleId } = useParams<{ projectId: string; cycleId: string }>();
  const cycleQ = useQuery({
    queryKey: qk.cycle(cycleId),
    queryFn: async () => (await getServices()).deliveryCycles.get(cycleId),
  });
  const previewsQ = useQuery({
    queryKey: [...qk.cycle(cycleId), "transitions"],
    queryFn: async () => (await getServices()).deliveryCycles.nextTransitions(cycleId),
  });
  const execQ = useQuery({
    queryKey: qk.cycleExecutions(cycleId),
    queryFn: async () => (await getServices()).executions.listByCycle(cycleId),
  });

  const cycle = cycleQ.data;
  const stages =
    cycle && previewsQ.data
      ? buildForgeStages(cycle.type, cycle.state, previewsQ.data, {
          runningExecutions: execQ.data?.filter((e) => e.status === "STARTED").length,
        })
      : [];

  return (
    <div>
      <h1 className="mb-2 text-xl font-semibold">Cycle Forge — {cycle?.key}</h1>
      <p className="mb-4 text-[var(--muted)]">{cycle?.objective}</p>
      <LifecycleForge stages={stages} />
      <section className="mt-6">
        <h2 className="text-sm font-semibold">Transition preview (server)</h2>
        <ul className="mt-2 space-y-2 text-xs">
          {previewsQ.data?.map((p) => (
            <li key={p.command} className="rounded border border-[var(--border)] p-2 font-mono">
              {p.command} → {p.target_state}: {p.allowed ? "allowed" : "blocked"}
              {p.guard_results.map((g: { guard: string; ok: boolean; reason?: string }) => (
                <div key={g.guard} className="text-[var(--muted)]">
                  {g.guard}: {g.ok ? "ok" : g.reason}
                </div>
              ))}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
