"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import { CodeSearch } from "@/components/code/CodeSearch";
import { IndexStatusBar } from "@/components/code/IndexStatusBar";
import { MaterializationTimeline } from "@/components/repository/MaterializationTimeline";
import { RepositoryHeader } from "@/components/repository/RepositoryHeader";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";
import { useActiveCycleId } from "@/lib/hooks/use-active-cycle";
import { qk } from "@/lib/query/keys";

const TABS = [
  "repository",
  "code-graph",
  "workspaces",
  "commits",
  "index-history",
  "traceability",
  "search",
] as const;

export default function CodePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const search = useSearchParams();
  const tabParam = search.get("tab") ?? "repository";
  const tab = (TABS.includes(tabParam as (typeof TABS)[number])
    ? tabParam
    : "repository") as (typeof TABS)[number];
  const [query, setQuery] = useState("Ticket");

  const cycleId = useActiveCycleId(projectId);

  const repoQ = useQuery({
    queryKey: qk.repositoryForProject(projectId),
    queryFn: async () => (await getServices()).repositories.forProject(projectId),
  });

  const repoId = repoQ.data?.id;
  const wsQ = useQuery({
    queryKey: qk.repoWorkspace(repoId ?? ""),
    queryFn: async () => (await getServices()).repositories.workspace(repoId!),
    enabled: !!repoId,
  });

  const indexQ = useQuery({
    queryKey: ["canonicalIndex", repoId],
    queryFn: async () => (await getServices()).code.canonicalIndex(repoId!),
    enabled: !!repoId,
  });

  const matQ = useQuery({
    queryKey: qk.repoMaterializations(repoId ?? ""),
    queryFn: async () => (await getServices()).repositories.materializations(repoId!),
    enabled: !!repoId && tab === "repository",
  });

  const ledgerQ = useQuery({
    queryKey: qk.commitLedger(repoId ?? ""),
    queryFn: async () => (await getServices()).repositories.commitLedger(repoId!),
    enabled: !!repoId && tab === "commits",
  });

  const exWsQ = useQuery({
    queryKey: qk.executionWorkspaces(repoId ?? "", cycleId ?? undefined),
    queryFn: async () =>
      (await getServices()).repositories.executionWorkspaces(repoId!, {
        cycle_id: cycleId ?? undefined,
      }),
    enabled: !!repoId && tab === "workspaces",
  });

  const entitiesQ = useQuery({
    queryKey: qk.codeEntities(indexQ.data?.id ?? "", "files"),
    queryFn: async () =>
      (await getServices()).code.entities(indexQ.data!.id, { type: "FILE" }),
    enabled: !!indexQ.data?.id && tab === "repository",
  });

  const searchQ = useQuery({
    queryKey: qk.codeSearch(repoId ?? "", query),
    queryFn: async () => (await getServices()).code.search(repoId!, query),
    enabled: !!repoId && tab === "search" && query.length > 1,
  });

  const versionsQ = useQuery({
    queryKey: ["indexVersions", repoId],
    queryFn: async () => (await getServices()).code.listVersions(repoId!),
    enabled: !!repoId && tab === "index-history",
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Repository & Code</h1>
      <nav className="flex flex-wrap gap-2 text-xs">
        {TABS.map((t) => (
          <a
            key={t}
            href={`/projects/${projectId}/code?tab=${t}`}
            className={`rounded border px-2 py-1 ${tab === t ? "border-amber-500" : "border-[var(--border)]"}`}
          >
            {t}
          </a>
        ))}
      </nav>
      {repoQ.data && (
        <RepositoryHeader
          repository={repoQ.data}
          workspace={wsQ.data ?? null}
          canonicalIndex={indexQ.data ?? null}
        />
      )}
      <IndexStatusBar canonical={indexQ.data ?? null} />
      {tab === "repository" && (
        <>
          <MaterializationTimeline materializations={matQ.data ?? []} />
          <Panel title="Repository explorer" stateRail="neutral" actions={<FixtureBadge />}>
            <ul className="font-mono text-xs">
              {entitiesQ.data?.slice(0, 40).map((e) => (
                <li key={e.id}>{e.file_path ?? e.name}</li>
              ))}
            </ul>
          </Panel>
        </>
      )}
      {tab === "workspaces" && (
        <Panel title="Execution workspaces" stateRail="neutral" actions={<FixtureBadge />}>
          <ul className="space-y-2 text-xs">
            {exWsQ.data?.map((w) => (
              <li key={w.id} className="rounded border border-dashed border-amber-500/40 p-2">
                <div className="text-[10px] uppercase tracking-wide text-amber-400/80">
                  Not canonical
                </div>
                <div className="font-mono">
                  {w.key} · {w.state} · base {w.base_commit?.slice(0, 12) ?? "—"}
                </div>
                <div className="text-[var(--muted)]">{w.logical_location}</div>
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {tab === "commits" && (
        <Panel title="Revision ledger" stateRail="neutral">
          <ul className="font-mono text-xs">
            {ledgerQ.data?.map((e, i) => (
              <li key={`${e.sha}-${i}`}>
                {e.kind} · {e.label ?? e.sha.slice(0, 12)} · {e.cause ?? ""}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {tab === "search" && (
        <div>
          <input
            className="mb-2 w-full max-w-md rounded border border-[var(--border)] bg-[var(--raised)] px-2 py-1"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search symbols…"
          />
          {searchQ.data && <CodeSearch hits={searchQ.data} projectId={projectId} />}
        </div>
      )}
      {tab === "index-history" && (
        <Panel title="Index history" stateRail="neutral" actions={<FixtureBadge />}>
          <ul className="font-mono text-xs">
            {versionsQ.data?.map((v) => (
              <li key={v.id}>
                {v.key ?? v.kind} @ {(v.commit_sha.length <= 12 ? v.commit_sha : v.commit_sha.slice(0, 12))} —{" "}
                {v.status}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {(tab === "code-graph" || tab === "traceability") && (
        <Panel title={tab} stateRail="neutral" actions={<FixtureBadge />}>
          <p className="text-xs text-[var(--muted)]">
            Use Search to open symbols; lineage and spec links are indexed from the fixture world.
          </p>
        </Panel>
      )}
    </div>
  );
}
