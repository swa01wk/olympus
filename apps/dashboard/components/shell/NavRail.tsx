"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { projectNav } from "./nav-config";
import { cn } from "@/lib/utils";

export function NavRail({ projectId, cycleId }: { projectId: string; cycleId: string | null }) {
  const pathname = usePathname();
  const groups = projectNav(projectId, cycleId);

  return (
    <nav aria-label="Project navigation" className="flex w-56 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] p-2 text-sm">
      <Link href="/projects" className="mb-3 px-2 text-xs text-[var(--muted)] hover:text-amber-300">
        ← Projects
      </Link>
      {groups.map((g) => (
        <div key={g.id} className="mb-3">
          <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted)]">
            {g.label}
          </div>
          {g.items.map((item) => {
            const active = pathname === item.href.split("?")[0] || pathname?.startsWith(item.href.split("?")[0] + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "block rounded-md px-2 py-1.5 hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-amber-500",
                  active && "bg-white/10 text-amber-300",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
