"use client";

import { Button } from "@/components/primitives";
import { StreamStatus } from "@/components/shell/StreamStatus";
import type { CycleStreamSnapshot } from "@/src/api/sse/use-cycle-event-stream";
import type { DeliveryCycle } from "@/src/api/types/core";
import type { Project } from "@/src/api/types/core";

export function TopBar({
  project,
  cycles,
  cycleId,
  onCycleChange,
  stream,
  actorInitials = "OP",
  onNewCycle,
  onAskOlympus,
}: {
  project?: Project;
  cycles: DeliveryCycle[];
  cycleId: string;
  onCycleChange: (id: string) => void;
  stream: CycleStreamSnapshot;
  actorInitials?: string;
  onNewCycle?: () => void;
  onAskOlympus?: () => void;
}) {
  return (
    <header className="ol-top">
      <div className="ol-brand">
        <span className="ol-wordmark">Olympus</span>
      </div>
      <div className="ol-top-ctx">
        <span className="ol-top-proj">{project?.name ?? project?.key ?? "Project"}</span>
        <span className="ol-top-sep" aria-hidden="true">
          /
        </span>
        <label className="ol-cycle">
          <span className="ol-visually-hidden">Delivery cycle</span>
          <select
            value={cycleId}
            onChange={(e) => onCycleChange(e.target.value)}
            aria-label="Delivery cycle"
          >
            {cycles.map((c) => (
              <option key={c.id} value={c.id}>
                {c.key} · {c.objective.slice(0, 48)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="ol-top-r">
        <StreamStatus stream={stream} />
        <Button variant="quiet" onClick={onNewCycle} disabled={!project?.id} title="Create delivery cycle">
          New delivery cycle
        </Button>
        <Button variant="quiet" onClick={onAskOlympus} disabled={!cycleId} title="Orchestrator converse">
          Ask Olympus
        </Button>
        <span className="ol-avatar" title="Operator">
          {actorInitials}
        </span>
      </div>
    </header>
  );
}
