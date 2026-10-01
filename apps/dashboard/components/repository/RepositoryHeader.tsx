"use client";

import type { CodeIndexVersion, Repository, RepositoryWorkspace } from "@/lib/contracts/entity-types";
import { Panel } from "@/components/design/Panel";
import { KV } from "@/components/design/KV";
import { Sha } from "@/components/design/Sha";

export function RepositoryHeader({
  repository,
  workspace,
  canonicalIndex,
}: {
  repository: Repository;
  workspace: RepositoryWorkspace | null;
  canonicalIndex: CodeIndexVersion | null;
}) {
  const origin =
    repository.source_type === "GREENFIELD_MANAGED"
      ? "Olympus Managed · LOCAL"
      : `${repository.provider} ${repository.remote_url ?? ""}`;

  return (
    <Panel title="Repository & Code" stateRail="neutral">
      <p className="mb-3 text-xs text-[var(--muted)]">
        Source code lives in Git — Olympus stores metadata, workspaces, and indexes only (README §5.9).
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        <KV label="Origin" value={origin} />
        <KV label="Authentication" value="CONNECTED" />
        <KV label="Branch" value={repository.default_branch} />
        <KV
          label="Canonical SHA"
          value={
            <span data-testid="repository-canonical-sha">
              <Sha sha={repository.canonical_commit} role="canonical" />
            </span>
          }
        />
        <KV
          label="Released SHA"
          value={
            <span data-testid="repository-released-sha">
              <Sha sha={repository.released_commit} role="released" />
            </span>
          }
        />
        <KV label="Workspace" value={workspace ? `${workspace.key} · ${workspace.state}` : "—"} />
        <KV label="Code index" value={canonicalIndex?.key ?? canonicalIndex?.scope_ref ?? "—"} />
        <KV label="Repository status" value={repository.status} />
      </div>
    </Panel>
  );
}
