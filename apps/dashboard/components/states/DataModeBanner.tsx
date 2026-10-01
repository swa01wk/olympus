"use client";

import { getDataMode, getFixtureScenario } from "@/lib/config/data-mode";

export function DataModeBanner() {
  if (getDataMode() !== "fixture") return null;
  return (
    <div
      role="status"
      className="border-b border-amber-500/40 bg-amber-500/10 px-4 py-2 text-center text-xs font-medium text-amber-200"
    >
      FIXTURE DATA — scenario: {getFixtureScenario()} — not operational state
    </div>
  );
}
