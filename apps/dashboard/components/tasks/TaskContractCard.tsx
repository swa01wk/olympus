"use client";

import { KV, Panel, StatusBadge } from "@/components/primitives";

export function TaskContractCard({
  contract,
}: {
  contract: {
    key: string;
    version: number;
    status: string;
    body: Record<string, unknown>;
    content_hash: string | null;
  } | null | undefined;
  loading?: boolean;
}) {
  if (!contract) {
    return (
      <Panel title="Task contract" sub="No issued contract for this task yet.">
        <p className="text-sm ol-muted">Contracts pin inputs, scope, and verification before execution.</p>
      </Panel>
    );
  }

  const body = contract.body;
  return (
    <Panel title="Task contract" sub={`${contract.key} · v${contract.version}`}>
      <div className="mb-3">
        <StatusBadge status={contract.status} />
      </div>
      <KV
        rows={Object.entries(body).map(([k, v]) => [
          k,
          typeof v === "object" ? JSON.stringify(v) : String(v),
        ])}
      />
      {contract.content_hash && (
        <p className="text-xs ol-muted mt-3">Hash: {contract.content_hash.slice(0, 16)}…</p>
      )}
    </Panel>
  );
}
