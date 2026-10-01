"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";

export default function ReleasesListPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const q = useQuery({
    queryKey: qk.releases(projectId),
    queryFn: async () => (await getServices()).release.list(projectId),
  });
  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Releases</h1>
      <ul className="space-y-2">
        {q.data?.map((r) => (
          <li key={r.id}>
            <Link href={`/releases/${r.id}`} className="font-mono text-amber-300 underline">
              {r.key}
            </Link>{" "}
            — {r.status}
          </li>
        ))}
      </ul>
    </div>
  );
}
