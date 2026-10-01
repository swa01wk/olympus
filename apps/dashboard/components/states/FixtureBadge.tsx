"use client";

import { getDataMode } from "@/lib/config/data-mode";

export function FixtureBadge({ className }: { className?: string }) {
  if (getDataMode() !== "fixture") return null;
  return (
    <span
      className={`inline-flex items-center rounded border border-amber-700/60 bg-amber-950/40 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-amber-300 ${className ?? ""}`}
      title="Data from fixture services"
    >
      Fixture
    </span>
  );
}
