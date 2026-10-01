"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { StatusBadge } from "@/components/status/StatusBadge";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";

export default function CyclesListPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const q = useQuery({
    queryKey: qk.cycles(projectId),
    queryFn: async () => (await getServices()).deliveryCycles.list(projectId),
  });
  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Delivery Cycles</h1>
      <ul className="space-y-2">
        {q.data?.map((c) => (
          <li key={c.id}>
            <Link
              href={`/projects/${projectId}/cycles/${c.id}`}
              className="flex flex-wrap items-center gap-2 rounded border border-[var(--border)] p-3 hover:bg-[var(--raised)]"
            >
              <span className="font-mono text-amber-300">{c.key}</span>
              <span>{c.type}</span>
              <StatusBadge value={c.state} preferred="running" />
              <span className="text-[var(--muted)]">{c.objective}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
