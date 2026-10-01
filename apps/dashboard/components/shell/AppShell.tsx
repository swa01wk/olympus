"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScenarioControlBar } from "@/components/dev/ScenarioControlBar";
import { DataModeBanner } from "@/components/states/DataModeBanner";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const inProject = /^\/projects\/[^/]+/.test(pathname ?? "");

  return (
    <div className="flex min-h-screen flex-col bg-[var(--background)] text-[var(--foreground)]">
      <DataModeBanner />
      <ScenarioControlBar />
      {inProject ? (
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      ) : (
        <div className="flex flex-1">
          <nav
            aria-label="Primary"
            className="flex w-52 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] p-3 text-sm"
          >
            <div className="mb-4 px-2 font-semibold tracking-tight text-amber-400">Olympus</div>
            <Link
              href="/projects"
              className={cn(
                "rounded-md px-2 py-2 hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-amber-500",
                pathname === "/projects" && "bg-white/10 text-amber-300",
              )}
            >
              Projects
            </Link>
            <Link href="/inbox" className="rounded-md px-2 py-2 hover:bg-white/5">
              Human Attention
            </Link>
            <Link href="/audit" className="rounded-md px-2 py-2 hover:bg-white/5">
              Audit
            </Link>
          </nav>
          <main className="flex-1 overflow-auto p-6">{children}</main>
        </div>
      )}
    </div>
  );
}
