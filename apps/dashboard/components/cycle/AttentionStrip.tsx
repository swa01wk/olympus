"use client";

import { Button, StatusBadge } from "@/components/primitives";
import type { AttentionItem } from "@/src/control-plane/attention";
import type { DeliveryCycle } from "@/src/api/types/core";
import { stageIndex, stagesForCycleType } from "@/src/control-plane/stage-lanes";

export function AttentionStrip({
  cycle,
  items,
  onInspect,
  onWhy,
}: {
  cycle: DeliveryCycle;
  items: AttentionItem[];
  onInspect: (item: AttentionItem) => void;
  onWhy: () => void;
}) {
  const top = items[0];
  const stages = stagesForCycleType(cycle.type);
  const idx = stageIndex(cycle.type, cycle.state);

  if (!top) {
    const next = stages[idx + 1];
    return (
      <div className="ol-attn is-calm" role="status">
        <StatusBadge status="running" label="Nothing needs you" />
        <div className="ol-attn-t">
          <strong>Olympus is progressing {cycle.state.replace(/_/g, " ")} on its own.</strong>
          <span className="ol-attn-sub">
            {next
              ? `${next.state.replace(/_/g, " ")} begins when its preconditions pass.`
              : "Cycle complete or terminal."}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="ol-attn" role="status">
      <StatusBadge
        status={top.uiStatusKey}
        label={items.length > 1 ? `${items.length} need you` : "Needs you"}
      />
      <div className="ol-attn-t">
        <strong>{top.headline}</strong>
        <span className="ol-attn-sub">{top.kind} · state → reason → permitted action</span>
      </div>
      <div className="ol-attn-a">
        <Button onClick={onWhy}>Why this state?</Button>
        <Button variant="primary" onClick={() => onInspect(top)}>
          Inspect
        </Button>
      </div>
    </div>
  );
}
