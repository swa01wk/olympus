"use client";

import Link from "next/link";
import { useQueries, useQuery } from "@tanstack/react-query";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import { StatusBadge } from "@/components/status/StatusBadge";
import { FixtureBadge } from "@/components/states/FixtureBadge";
export default function ProjectsPage() {
  const { data: projects, isLoading, error } = useQuery({
    queryKey: qk.projects(),
    queryFn: async () => (await getServices()).projects.list(),
  });

  const summaries = useQueries({
    queries: (projects ?? []).map((p) => ({
      queryKey: [...qk.project(p.id), "summary"],
      queryFn: async () => (await getServices()).projects.summary(p.id),
    })),
  });

  const historyQueries = useQueries({
    queries: (projects ?? []).map((p) => ({
      queryKey: [...qk.cycles(p.id), "history"],
      queryFn: async () => {
        const svc = await getServices();
        const cycles = await svc.deliveryCycles.list(p.id);
        const releases = await svc.release.list(p.id);
        return cycles.map((c) => {
          const rel = releases.find((r) => r.delivery_cycle_id === c.id && r.status === "RELEASED");
          return {
            key: c.key,
            type: c.type,
            state: c.state,
            releaseKey: rel?.key ?? null,
          };
        });
      },
    })),
  });

  if (isLoading) return <p className="text-[var(--muted)]">Loading projects…</p>;
  if (error) return <p className="text-rose-400">{(error as Error).message}</p>;

  return (
    <div>
      <div className="mb-4 flex items-center gap-2">
        <h1 className="text-xl font-semibold">Projects</h1>
        <FixtureBadge />
      </div>
      <ul className="space-y-4">
        {projects?.map((p, i) => {
          const summary = summaries[i]?.data;
          const history = historyQueries[i]?.data ?? [];
          return (
            <li key={p.id} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
              <Link href={`/projects/${p.id}`} className="flex flex-wrap items-center justify-between gap-2 hover:opacity-90">
                <span>
                  <span className="font-mono text-amber-300">{p.key}</span> — {p.name}
                </span>
                <StatusBadge value={p.readiness_state} preferred="complete" />
              </Link>
              {summary && (
                <dl className="mt-3 grid gap-2 text-xs md:grid-cols-4">
                  <div>
                    <dt className="text-[var(--muted)]">Active cycle</dt>
                    <dd className="font-mono">{summary.active_cycle_key ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--muted)]">Stage</dt>
                    <dd>{summary.stage ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--muted)]">Tasks / running EX</dt>
                    <dd>
                      {summary.task_count} / {summary.running_executions}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[var(--muted)]">Canonical SHA</dt>
                    <dd className="font-mono truncate">{summary.canonical_sha?.slice(0, 12) ?? "—"}</dd>
                  </div>
                </dl>
              )}
              <div className="mt-3">
                <h3 className="text-[10px] font-semibold uppercase text-[var(--muted)]">Delivery history</h3>
                <ul className="mt-1 space-y-1 font-mono text-[11px]">
                  {history.map((h) => (
                    <li key={h.key}>
                      {h.key} {h.type} → {h.state}
                      {h.releaseKey ? ` / ${h.releaseKey} RELEASED` : ""}
                    </li>
                  ))}
                </ul>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
