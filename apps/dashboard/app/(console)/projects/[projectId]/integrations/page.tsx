"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "next/navigation";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";

export default function IntegrationsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const search = useSearchParams();
  const tab = search.get("tab") ?? "topology";

  const connectorsQ = useQuery({
    queryKey: ["connectors", projectId],
    queryFn: async () => (await getServices()).connectors.list(projectId),
  });
  const inboundQ = useQuery({
    queryKey: ["inbound", projectId],
    queryFn: async () => (await getServices()).connectors.inboundEvents(projectId),
  });
  const actionsQ = useQuery({
    queryKey: ["connectorActions", projectId],
    queryFn: async () => (await getServices()).connectors.actions(projectId),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Integrations</h1>
      <nav className="flex flex-wrap gap-2 text-xs">
        {(["topology", "inbound", "outbound", "reconciliation"] as const).map((t) => (
          <a
            key={t}
            href={`/projects/${projectId}/integrations?tab=${t}`}
            className={`rounded border px-2 py-1 ${tab === t ? "border-amber-500" : "border-[var(--border)]"}`}
          >
            {t}
          </a>
        ))}
      </nav>
      {tab === "topology" && (
        <Panel title="Connectors" stateRail="neutral" actions={<FixtureBadge />}>
          <ul className="font-mono text-xs">
            {connectorsQ.data?.map((c) => (
              <li key={c.id}>
                {c.name} — {c.connector_type}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {tab === "inbound" && (
        <Panel title="Inbound events" stateRail="running" actions={<FixtureBadge />}>
          <ul className="text-xs">
            {inboundQ.data?.map((e) => (
              <li key={e.id}>
                {e.source} {e.event_type} {e.status} {e.correlation_id?.slice(0, 8)}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      {tab === "outbound" && (
        <Panel title="Outbound pipeline" stateRail="neutral" actions={<FixtureBadge />}>
          <p className="text-xs text-[var(--muted)]">{actionsQ.data?.length ?? 0} connector actions logged.</p>
        </Panel>
      )}
      {tab === "reconciliation" && (
        <Panel title="Reconciliation" stateRail="waiting" actions={<FixtureBadge />}>
          <p className="text-xs text-[var(--muted)]">Reconciliation items from fixture connectors module.</p>
        </Panel>
      )}
    </div>
  );
}
