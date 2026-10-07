"use client";

import {
  formatStageLabel,
  SPINE_GLYPH,
  SPINE_STATUS_WORD,
  spineStatusForStage,
  type SpineStageStatus,
} from "@/lib/studio-spine";
import type { TransitionPreview } from "@/src/api/types/core";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";
import { stagesForType } from "@/lib/studio-spine";
import { cn } from "@/lib/utils";

const TONE_CLASS: Record<SpineStageStatus, string> = {
  done: "ol-spine-done",
  current: "ol-spine-current",
  waiting: "ol-spine-waiting",
  blocked: "ol-spine-blocked",
  future: "ol-spine-future",
};

export function StageSpine({
  cycleType,
  cycleState,
  selectedStage,
  inboxStages,
  nextTransitions,
  onSelectStage,
}: {
  cycleType: DeliveryCycleType;
  cycleState: string;
  selectedStage: string;
  inboxStages: Set<string>;
  nextTransitions: TransitionPreview[];
  onSelectStage: (stage: string) => void;
}) {
  const stages = stagesForType(cycleType);

  return (
    <ol className="ol-spine" aria-label="Delivery stages">
      {stages.map((stage) => {
        const status = spineStatusForStage(stage, cycleState, stages, {
          inboxStages,
          nextTransitions,
        });
        const selected = stage === selectedStage;
        const label = formatStageLabel(stage);
        return (
          <li key={stage}>
            <button
              type="button"
              className={cn("ol-spine-item", TONE_CLASS[status], selected && "is-selected")}
              aria-current={selected ? "step" : undefined}
              aria-label={`${label} · ${SPINE_STATUS_WORD[status]}`}
              onClick={() => onSelectStage(stage)}
            >
              <span className="ol-spine-glyph" aria-hidden="true">
                {SPINE_GLYPH[status]}
              </span>
              <span className="ol-spine-label">{label}</span>
              <span className="ol-spine-word">{SPINE_STATUS_WORD[status]}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
