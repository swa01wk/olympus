"use client";

import { ContextBar } from "./ContextBar";
import { NavRail } from "./NavRail";
import { CommandPalette } from "./CommandPalette";
import { EntityDrawer } from "@/components/entity/EntityDrawer";
import { useActiveCycleId, useProjectId } from "@/lib/hooks/use-active-cycle";

export function ProjectShell({ children }: { children: React.ReactNode }) {
  const projectId = useProjectId();
  const cycleId = useActiveCycleId(projectId);

  if (!projectId) return <>{children}</>;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <ContextBar />
      <div className="flex min-h-0 flex-1">
        <NavRail projectId={projectId} cycleId={cycleId} />
        <div className="min-w-0 flex-1 overflow-auto p-6">{children}</div>
      </div>
      <CommandPalette projectId={projectId} />
      <EntityDrawer />
    </div>
  );
}
