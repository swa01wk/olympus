"use client";

import { ChatPanel } from "@/components/studio/chat/ChatPanel";
import { DrawerPanel } from "@/components/dialogs/DrawerPanel";
import { useDeliveryCycle } from "@/src/api/hooks/use-olympus-queries";
import { useCycleEventStream } from "@/src/api/sse/use-cycle-event-stream";
import { useCallback, useRef } from "react";

export function AskOlympusDrawer({
  open,
  onClose,
  projectId,
  cycleId,
}: {
  open: boolean;
  onClose: () => void;
  projectId: string | null;
  cycleId: string | null;
}) {
  const cycle = useDeliveryCycle(cycleId ?? undefined);
  const turnHandlerRef = useRef<(payload: Record<string, unknown>) => void>(() => {});
  const registerTurnCompletedHandler = useCallback(
    (handler: (payload: Record<string, unknown>) => void) => {
      turnHandlerRef.current = handler;
    },
    [],
  );

  useCycleEventStream(cycleId ?? undefined, {
    enabled: open && Boolean(cycleId),
    onEvent: (event) => {
      if (event.event_type === "orchestrator.turn_completed") {
        turnHandlerRef.current(event.payload ?? {});
      }
    },
  });

  const close = () => {
    onClose();
  };

  return (
    <DrawerPanel open={open} onClose={close} label="Orchestrator" title="Ask Olympus">
      {open && projectId && cycleId && cycle.data ? (
        <ChatPanel
          projectId={projectId}
          cycle={cycle.data}
          onTurnCompleted={registerTurnCompletedHandler}
          onSelectStage={() => {}}
          compact
        />
      ) : (
        <p className="text-sm ol-muted">
          Select a delivery cycle to converse. The orchestrator schedules agent work against that
          cycle.
        </p>
      )}
    </DrawerPanel>
  );
}
