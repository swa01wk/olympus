"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ImpactFlow } from "@/components/impact/ImpactFlow";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";

export default function ImpactExplorerPage() {
  const { iaId } = useParams<{ iaId: string }>();
  const q = useQuery({
    queryKey: ["impactAssessment", iaId],
    queryFn: async () => (await getServices()).impact.get(iaId),
  });

  if (!q.data) return <p>Loading…</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Impact Explorer</h1>
      <Panel title="Assessment" stateRail="complete" actions={<FixtureBadge />}>
        <p className="font-mono text-xs">status {q.data.status}</p>
      </Panel>
      <ImpactFlow assessment={q.data} />
      <ul className="space-y-2 text-xs">
        {q.data.items.map((item) => (
          <li key={item.id} className="rounded border border-[var(--border)] p-2">
            <span className="font-mono text-amber-300">{item.stable_key}</span> — {item.kind}
            <p className="mt-1 text-[var(--muted)]">
              why: {item.path.map((p) => `${p.from} -${p.relation}-> ${p.to}`).join(" · ")}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
