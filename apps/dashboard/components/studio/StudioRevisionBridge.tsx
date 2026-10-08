"use client";

import { useStudioFocus } from "@/lib/studio-focus";
import { useStudioRevision } from "@/lib/studio-revision";
import type { DomainEventPayload } from "@/src/api/types/core";
import { useEffect, useRef } from "react";

export function StudioRevisionBridge({
  onRegister,
}: {
  onRegister: (handler: (event: DomainEventPayload) => void) => void;
}) {
  const focus = useStudioFocus();
  const focusRef = useRef(focus);
  focusRef.current = focus;
  const { onDomainEvent } = useStudioRevision();

  useEffect(() => {
    onRegister((event) => {
      if (event.event_type !== "revision.requested" && event.event_type !== "revision.completed") {
        return;
      }
      onDomainEvent(
        event.event_type,
        (event.payload ?? {}) as Record<string, unknown>,
        focusRef.current,
      );
    });
  }, [onDomainEvent, onRegister]);

  return null;
}
