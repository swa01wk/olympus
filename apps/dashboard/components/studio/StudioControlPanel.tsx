"use client";

import { StageSpine } from "@/components/studio/StageSpine";
import { StreamStatus } from "@/components/shell/StreamStatus";
import type { CycleStreamSnapshot } from "@/src/api/sse/use-cycle-event-stream";
import type { DeliveryCycle, Project, TransitionPreview } from "@/src/api/types/core";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";
import { useRouter } from "next/navigation";

export function StudioControlPanel({
  projects,
  project,
  cycles,
  cycle,
  cycleId,
  onCycleChange,
  stream,
  inboxCount,
  selectedStage,
  inboxStages,
  nextTransitions,
  onSelectStage,
}: {
  projects: Project[];
  project?: Project;
  cycles: DeliveryCycle[];
  cycle: DeliveryCycle;
  cycleId: string;
  onCycleChange: (id: string) => void;
  stream: CycleStreamSnapshot;
  inboxCount: number;
  selectedStage: string;
  inboxStages: Set<string>;
  nextTransitions: TransitionPreview[];
  onSelectStage: (stage: string) => void;
}) {
  const router = useRouter();

  return (
    <aside className="ol-studio-control" aria-label="Control panel">
      <div className="ol-studio-pickers">
        <label className="ol-studio-field">
          <span className="ol-label">Project</span>
          <select
            value={project?.id ?? ""}
            aria-label="Project"
            onChange={(e) => {
              const id = e.target.value;
              if (!id) return;
              router.push(`/projects/${id}/cycles/${cycleId}/studio`);
            }}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.key} · {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="ol-studio-field">
          <span className="ol-label">Cycle</span>
          <select value={cycleId} aria-label="Delivery cycle" onChange={(e) => onCycleChange(e.target.value)}>
            {cycles.map((c) => (
              <option key={c.id} value={c.id}>
                {c.key} · {c.objective.slice(0, 40)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="ol-studio-meta">
        <StreamStatus stream={stream} />
        <span className="ol-studio-inbox">
          Inbox ({inboxCount})
        </span>
      </div>
      <StageSpine
        cycleType={cycle.type as DeliveryCycleType}
        cycleState={cycle.state}
        selectedStage={selectedStage}
        inboxStages={inboxStages}
        nextTransitions={nextTransitions}
        onSelectStage={onSelectStage}
      />
    </aside>
  );
}
