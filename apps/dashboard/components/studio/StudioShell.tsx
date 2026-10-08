"use client";

import { ChatPanel } from "@/components/studio/chat/ChatPanel";
import { ChangesRequestedFeedback } from "@/components/studio/ChangesRequestedFeedback";
import { ProductSpecView } from "@/components/studio/ProductSpecView";
import { RevisionActivityPanel } from "@/components/studio/RevisionActivityPanel";
import { DecisionPanel } from "@/components/studio/DecisionPanel";
import { NextStepBar } from "@/components/studio/NextStepBar";
import { StageWorkspace } from "@/components/studio/workspace/StageWorkspace";
import { StudioControlPanel } from "@/components/studio/StudioControlPanel";
import { Button } from "@/components/primitives";
import { formatStageLabel } from "@/lib/studio-spine";
import { useMediaQuery } from "@/lib/use-media-query";
import type { CycleStreamSnapshot } from "@/src/api/sse/use-cycle-event-stream";
import type { DeliveryCycle, InboxItem, Project, TransitionPreview } from "@/src/api/types/core";
import { cn } from "@/lib/utils";
import { useState } from "react";

type StudioTab = "stages" | "chat" | "workspace";

export function StudioShell({
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
  onFollowCycle,
  showFollowBanner,
  registerTurnCompletedHandler,
  inboxItems,
  onStudioInvalidate,
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
  onFollowCycle: () => void;
  showFollowBanner: boolean;
  registerTurnCompletedHandler: (
    handler: (payload: Record<string, unknown>) => void,
  ) => void;
  inboxItems: InboxItem[];
  onStudioInvalidate: () => void;
}) {
  const compact = useMediaQuery("(max-width: 1023px)");
  const [tab, setTab] = useState<StudioTab>("workspace");
  const [productSpecOpen, setProductSpecOpen] = useState(false);
  const projectIdForSpec = project?.id ?? cycle.project_id;

  const control = (
    <StudioControlPanel
      projects={projects}
      project={project}
      cycles={cycles}
      cycle={cycle}
      cycleId={cycleId}
      onCycleChange={onCycleChange}
      stream={stream}
      inboxCount={inboxCount}
      selectedStage={selectedStage}
      inboxStages={inboxStages}
      nextTransitions={nextTransitions}
      onSelectStage={onSelectStage}
      onOpenProductSpec={() => setProductSpecOpen(true)}
    />
  );

  const chat = (
    <section className="ol-studio-chat" aria-label="Chat">
      <header className="ol-studio-pane-head">
        <h2 className="ol-section">Chat</h2>
      </header>
      <ChatPanel
        projectId={project?.id ?? cycle.project_id}
        cycle={cycle}
        onTurnCompleted={registerTurnCompletedHandler}
        onSelectStage={onSelectStage}
        compact={compact}
      />
    </section>
  );

  const workspace = (
    <section className="ol-studio-workspace" aria-label="Workspace">
      {showFollowBanner && (
        <div className="ol-studio-follow" role="status">
          <span>
            Cycle moved to {formatStageLabel(cycle.state)} —{" "}
          </span>
          <Button variant="quiet" onClick={onFollowCycle}>
            Follow
          </Button>
        </div>
      )}
      <header className="ol-studio-ws-head">
        <div>
          <p className="ol-label">Stage</p>
          <h1 className="ol-section">{formatStageLabel(selectedStage)}</h1>
        </div>
        <div className="ol-studio-ws-meta">
          <span className="ol-id">{cycle.key}</span>
          <span className="ol-body-sm ol-muted">Machine state · {cycle.state}</span>
        </div>
      </header>
      <DecisionPanel
        stage={selectedStage}
        cycleType={cycle.type}
        inbox={inboxItems}
        projectId={project?.id ?? cycle.project_id}
        nextTransitions={nextTransitions}
        onDecided={onStudioInvalidate}
      />
      <ChangesRequestedFeedback
        cycleId={cycleId}
        cycleType={cycle.type}
        stage={selectedStage}
      />
      <RevisionActivityPanel />
      {productSpecOpen && (
        <div className="ol-product-spec-overlay">
          <ProductSpecView projectId={projectIdForSpec} />
          <Button variant="quiet" type="button" onClick={() => setProductSpecOpen(false)}>
            Close product spec
          </Button>
        </div>
      )}
      <StageWorkspace
        projectId={project?.id ?? cycle.project_id}
        cycle={cycle}
        stage={selectedStage}
        inbox={inboxItems}
      />
      {selectedStage === cycle.state && (
        <NextStepBar
          cycleId={cycleId}
          cycleState={cycle.state}
          nextTransitions={nextTransitions}
          onTransition={onStudioInvalidate}
        />
      )}
    </section>
  );

  if (compact) {
    return (
      <div className="ol-studio ol-studio-compact">
        <div className="ol-studio-tabs" role="tablist" aria-label="Studio panes">
          {(["stages", "chat", "workspace"] as const).map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={cn("ol-studio-tab", tab === id && "is-on")}
              onClick={() => setTab(id)}
            >
              {id === "stages" ? "Stages" : id === "chat" ? "Chat" : "Workspace"}
            </button>
          ))}
        </div>
        <div className="ol-studio-tabpanel">
          {tab === "stages" && control}
          {tab === "chat" && chat}
          {tab === "workspace" && workspace}
        </div>
      </div>
    );
  }

  return (
    <div className="ol-studio">
      {control}
      {chat}
      {workspace}
    </div>
  );
}
