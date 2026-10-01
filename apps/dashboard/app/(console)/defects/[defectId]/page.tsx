"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { getServices } from "@/lib/api/services";

export default function DefectPage() {
  const { defectId } = useParams<{ defectId: string }>();
  const defectQ = useQuery({
    queryKey: ["defect", defectId],
    queryFn: async () => (await getServices()).defects.get(defectId),
  });
  const reproQ = useQuery({
    queryKey: ["reproductions", defectId],
    queryFn: async () => (await getServices()).defects.reproductions(defectId),
  });
  const traceQ = useQuery({
    queryKey: ["trace", defectId],
    queryFn: async () => (await getServices()).defects.trace(defectId),
  });
  const rcaQ = useQuery({
    queryKey: ["rca", defectId],
    queryFn: async () => (await getServices()).defects.rca(defectId),
  });

  const d = defectQ.data;
  if (!d) return <p>Loading…</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Defect {d.key}</h1>
      <FixtureBadge />
      <Panel title="Failure path" stateRail="failed">
        <p className="text-xs">{d.title}</p>
        <p className="mt-2 font-mono text-[11px] text-[var(--muted)]">status {d.status}</p>
      </Panel>
      <Panel title="Reproductions" stateRail="neutral" actions={<FixtureBadge />}>
        <ul className="text-xs">
          {reproQ.data?.map((r) => (
            <li key={r.id}>
              {r.phase} — {r.status}
            </li>
          ))}
        </ul>
      </Panel>
      {traceQ.data && (
        <Panel title="Trace correlation" stateRail="neutral" actions={<FixtureBadge />}>
          <ul className="font-mono text-[10px]">
            {traceQ.data.candidates?.map((c) => (
              <li key={c.stable_key}>{c.stable_key} ({c.evidence_basis})</li>
            ))}
          </ul>
        </Panel>
      )}
      {rcaQ.data && (
        <Panel title="Root cause" stateRail="waiting" actions={<FixtureBadge />}>
          <p className="text-sm">{rcaQ.data.summary}</p>
          <p className="text-xs text-[var(--muted)]">{rcaQ.data.knowledge_class}</p>
        </Panel>
      )}
    </div>
  );
}
