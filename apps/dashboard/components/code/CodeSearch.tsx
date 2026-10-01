"use client";

import Link from "next/link";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import type { CodeEntity } from "@/lib/contracts/entity-types";

export function CodeSearch({
  hits,
  projectId,
}: {
  hits: CodeEntity[];
  projectId: string;
}) {
  return (
    <div>
      <FixtureBadge className="mb-2" />
      <ul className="space-y-1 text-xs">
        {hits.map((e) => (
          <li key={e.id} className="rounded border border-[var(--border)] p-2">
            <span className="font-mono text-amber-300">{e.stable_key}</span>{" "}
            <span className="text-[var(--muted)]">{e.type}</span>
            <Link
              href={`/projects/${projectId}/code?tab=explorer&entity=${e.id}`}
              className="ml-2 text-sky-400 underline"
            >
              Open
            </Link>
          </li>
        ))}
        {hits.length === 0 && <li className="text-[var(--muted)]">No hits</li>}
      </ul>
    </div>
  );
}
