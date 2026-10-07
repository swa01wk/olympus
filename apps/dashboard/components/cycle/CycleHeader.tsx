"use client";

import { Button } from "@/components/primitives";
import { LifecycleRibbon } from "@/components/cycle/LifecycleRibbon";
import Link from "next/link";
import { RemediationCycleNotice } from "@/components/truth/RemediationCycleNotice";
import { journeyDirection, journeyLabel } from "@/lib/journey-labels";
import { isNegativeTerminal, isTerminalCycleState, terminalConsequence } from "@/lib/cycle-terminal";
import { ExceptionState } from "@/components/truth/ExceptionState";
import type { DeliveryCycle } from "@/src/api/types/core";
import { ribbonStages, stageIndex, stagesForCycleType } from "@/src/control-plane/stage-lanes";

export function CycleHeader({
  cycle,
  projectId,
}: {
  cycle: DeliveryCycle;
  projectId?: string;
}) {
  const stages = ribbonStages(cycle.type, cycle.state);
  const idx = stageIndex(cycle.type, cycle.state);
  const currentIdx = idx >= 0 ? idx : stages.length - 1;
  const allStages = stagesForCycleType(cycle.type);

  return (
    <div className="ol-ch">
      <div className="ol-ch-row">
        <div className="ol-ch-l">
          <div className="ol-crumbs">
            <span className="ol-crumb">Project</span>
            <span className="ol-crumb">Cycle map</span>
          </div>
          <h1 className="ol-title">{cycle.objective}</h1>
          <div className="ol-ch-meta">
            <span className="ol-id">{cycle.key}</span>
            <span>{journeyLabel(cycle.type)}</span>
            <span className="ol-dotsep" aria-hidden="true">
              ·
            </span>
            <span>{journeyDirection(cycle.type)}</span>
            <span className="ol-dotsep" aria-hidden="true">
              ·
            </span>
            <span>State: {cycle.state}</span>
          </div>
        </div>
        <div className="ol-ch-r">
          <div className="ol-stagechip">
            <span className="ol-label">Stage</span>
            {allStages[currentIdx]?.laneCode ?? "—"} · {cycle.state}
          </div>
          {projectId && (
            <Button asChild variant="quiet" className="ol-ch-studio-link">
              <Link href={`/projects/${projectId}/cycles/${cycle.id}/studio`}>Open studio</Link>
            </Button>
          )}
        </div>
      </div>
      <LifecycleRibbon stages={stages} currentIndex={currentIdx} terminalState={cycle.state} />
      {cycle.type === "REMEDIATION" && <RemediationCycleNotice />}
      {isTerminalCycleState(cycle.state) && (
        <div className="ol-ribbon-terminal">
          <ExceptionState
            status={isNegativeTerminal(cycle.state) ? "failed" : "approved"}
            statusLabel={`Terminal · ${cycle.state}`}
            reason={`Lifecycle is fixed at ${cycle.state.replace(/_/g, " ")}.`}
            consequence={terminalConsequence(cycle.state)}
          />
        </div>
      )}
    </div>
  );
}
