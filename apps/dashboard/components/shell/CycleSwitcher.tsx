"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";

export function CycleSwitcher({ projectId }: { projectId: string }) {
  const pathname = usePathname();
  const search = useSearchParams();
  const cycleId = search.get("cycle");
  const { data: cycles } = useQuery({
    queryKey: qk.cycles(projectId),
    queryFn: async () => (await getServices()).deliveryCycles.list(projectId),
  });

  const base = pathname ?? `/projects/${projectId}`;
  const other = new URLSearchParams(search.toString());

  return (
    <div className="flex flex-wrap gap-1">
      {cycles?.map((c) => {
        other.set("cycle", c.id);
        const href = `${base.split("?")[0]}?${other.toString()}`;
        return (
          <Link
            key={c.id}
            href={href}
            className={`rounded border px-2 py-0.5 font-mono text-xs ${
              c.id === cycleId ? "border-amber-500 text-amber-300" : "border-[var(--border)]"
            }`}
          >
            {c.key}
          </Link>
        );
      })}
    </div>
  );
}
