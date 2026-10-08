"use client";

import { AppShell } from "@/components/shell/AppShell";
import { StudioProviders } from "@/components/studio/StudioProviders";
import { StudioRevisionBridge } from "@/components/studio/StudioRevisionBridge";
import { StudioShell } from "@/components/studio/StudioShell";
import { inboxStagesForCycle, stagesForType } from "@/lib/studio-spine";
import { invalidateStudioCycle } from "@/src/api/hooks/invalidate-cycle";
import {
  useDeliveryCycle,
  useDeliveryCycles,
  useInbox,
  useProject,
  useProjects,
} from "@/src/api/hooks/use-olympus-queries";
import { useNextTransitions } from "@/src/api/hooks/use-studio-queries";
import { useCycleEventStream } from "@/src/api/sse/use-cycle-event-stream";
import type { DomainEventPayload } from "@/src/api/types/core";
import type { DeliveryCycleType } from "@/src/control-plane/stage-lanes";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useRef } from "react";

export function StudioScreen({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();

  const projects = useProjects();
  const project = useProject(projectId);
  const cycles = useDeliveryCycles(projectId);
  const cycle = useDeliveryCycle(cycleId);
  const inbox = useInbox({ cycleId });
  const transitions = useNextTransitions(cycleId);

  const invalidate = useCallback(() => {
    invalidateStudioCycle(queryClient, { projectId, cycleId });
  }, [queryClient, projectId, cycleId]);

  const turnHandlerRef = useRef<(payload: Record<string, unknown>) => void>(() => {});
  const revisionHandlerRef = useRef<(event: DomainEventPayload) => void>(() => {});
  const registerRevisionHandler = useCallback((handler: (event: DomainEventPayload) => void) => {
    revisionHandlerRef.current = handler;
  }, []);
  const registerTurnCompletedHandler = useCallback(
    (handler: (payload: Record<string, unknown>) => void) => {
      turnHandlerRef.current = handler;
    },
    [],
  );

  const stream = useCycleEventStream(cycleId, {
    invalidate,
    onEvent: (event) => {
      if (event.event_type === "orchestrator.turn_completed") {
        turnHandlerRef.current(event.payload ?? {});
      }
      revisionHandlerRef.current(event);
    },
  });

  const cycleRow = cycle.data;
  const stageParam = searchParams.get("stage");
  const orderedStages = cycleRow ? stagesForType(cycleRow.type as DeliveryCycleType) : [];
  const defaultStage = cycleRow?.state ?? "";
  const selectedStage =
    stageParam && orderedStages.includes(stageParam) ? stageParam : defaultStage;

  const inboxStages = useMemo(
    () =>
      cycleRow
        ? inboxStagesForCycle(inbox.data ?? [], cycleRow.type as DeliveryCycleType)
        : new Set<string>(),
    [inbox.data, cycleRow],
  );
  const inboxCount = (inbox.data ?? []).length;

  const showFollowBanner = Boolean(
    stageParam && cycleRow && stageParam !== cycleRow.state && orderedStages.includes(stageParam),
  );

  const setStage = (stage: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (stage === cycleRow?.state) params.delete("stage");
    else params.set("stage", stage);
    const q = params.toString();
    router.replace(`/projects/${projectId}/cycles/${cycleId}/studio${q ? `?${q}` : ""}`, {
      scroll: false,
    });
  };

  const onCycleChange = (id: string) => {
    const q = searchParams.toString();
    router.push(`/projects/${projectId}/cycles/${id}/studio${q ? `?${q}` : ""}`);
  };

  const onFollowCycle = () => {
    if (!cycleRow) return;
    setStage(cycleRow.state);
  };

  if (cycle.isLoading || !cycleRow) {
    return (
      <AppShell
        project={project.data}
        cycles={cycles.data ?? []}
        cycleId={cycleId}
        onCycleChange={onCycleChange}
        stream={stream}
      >
        <p className="ol-muted">Loading studio…</p>
      </AppShell>
    );
  }

  return (
    <AppShell
      project={project.data}
      cycles={cycles.data ?? []}
      cycleId={cycleId}
      onCycleChange={onCycleChange}
      stream={stream}
    >
      <StudioProviders>
        <StudioRevisionBridge onRegister={registerRevisionHandler} />
        <StudioShell
          projects={projects.data ?? []}
          project={project.data}
          cycles={cycles.data ?? []}
          cycle={cycleRow}
          cycleId={cycleId}
          onCycleChange={onCycleChange}
          stream={stream}
          inboxCount={inboxCount}
          selectedStage={selectedStage}
          inboxStages={inboxStages}
          nextTransitions={transitions.data ?? []}
          onSelectStage={setStage}
          onFollowCycle={onFollowCycle}
          showFollowBanner={showFollowBanner}
          registerTurnCompletedHandler={registerTurnCompletedHandler}
          inboxItems={inbox.data ?? []}
          onStudioInvalidate={invalidate}
        />
      </StudioProviders>
    </AppShell>
  );
}
