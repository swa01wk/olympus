"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import { Sha } from "@/components/design/Sha";

export function RepositorySummaryChip({ projectId }: { projectId: string }) {
  const repoQ = useQuery({
    queryKey: qk.repositoryForProject(projectId),
    queryFn: async () => (await getServices()).repositories.forProject(projectId),
  });
  const indexQ = useQuery({
    queryKey: ["canonicalIndex", repoQ.data?.id ?? ""] as const,
    queryFn: async () => (await getServices()).code.canonicalIndex(repoQ.data!.id),
    enabled: !!repoQ.data?.id,
  });

  const repo = repoQ.data;
  if (!repo) return null;

  const origin =
    repo.source_type === "GREENFIELD_MANAGED"
      ? "Olympus Managed · LOCAL"
      : `GitHub ${repo.remote_url?.replace("https://github.com/", "") ?? "remote"}`;

  const indexKey = indexQ.data?.key ?? indexQ.data?.scope_ref ?? "—";

  return (
    <Link
      href={`/projects/${projectId}/code?tab=repository`}
      className="rounded border border-[var(--border)] bg-[var(--raised)] px-2 py-1 font-mono text-[10px] hover:border-amber-500/50"
      data-testid="repository-summary-chip"
    >
      Repository {repo.status} · {origin} · Branch {repo.default_branch}       · Canonical <Sha sha={repo.canonical_commit} role="canonical" className="text-amber-200" />
      {repo.released_commit && repo.released_commit !== repo.canonical_commit && (
        <>
          {" "}
          · Released <Sha sha={repo.released_commit} role="released" className="text-emerald-300" />
        </>
      )}{" "}
      · Index {indexKey}
    </Link>
  );
}
