"use client";

import { useOperatorDialogs } from "@/components/providers/OperatorDialogsProvider";
import { NavRail } from "@/components/shell/NavRail";
import { TopBar } from "@/components/shell/TopBar";
import type { CycleStreamSnapshot } from "@/src/api/sse/use-cycle-event-stream";
import type { DeliveryCycle, Project } from "@/src/api/types/core";
import type { LaneId } from "@/src/control-plane/lanes";
import type { ReactNode } from "react";
import { useEffect } from "react";

export function AppShell({
  project,
  cycles,
  cycleId,
  onCycleChange,
  stream,
  laneFlags,
  children,
}: {
  project?: Project;
  cycles: DeliveryCycle[];
  cycleId: string;
  onCycleChange: (id: string) => void;
  stream: CycleStreamSnapshot;
  laneFlags?: Partial<Record<LaneId, string>>;
  children: ReactNode;
}) {
  const { setShellContext, openIntake, openAskOlympus } = useOperatorDialogs();

  useEffect(() => {
    if (project?.id) {
      setShellContext({ projectId: project.id, cycleId });
    }
  }, [project?.id, cycleId, setShellContext]);

  return (
    <div className="ol-app">
      <TopBar
        project={project}
        cycles={cycles}
        cycleId={cycleId}
        onCycleChange={onCycleChange}
        stream={stream}
        onNewCycle={openIntake}
        onAskOlympus={openAskOlympus}
      />
      <div className="ol-body">
        <NavRail projectId={project?.id ?? ""} cycleId={cycleId} laneFlags={laneFlags} />
        <main className="ol-main">{children}</main>
      </div>
    </div>
  );
}
