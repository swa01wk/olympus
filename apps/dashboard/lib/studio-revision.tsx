"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { StudioFocus } from "@/lib/studio-focus";
import {
  parseRevisionCompleted,
  parseRevisionRequested,
  subjectMatchesFocus,
  type RevisionCompletedState,
  type RevisionRequestedState,
} from "@/lib/revision-tracker";

type RevisionStudioContextValue = {
  revising: RevisionRequestedState | null;
  completed: RevisionCompletedState | null;
  clearCompleted: () => void;
  onDomainEvent: (eventType: string, payload: Record<string, unknown>, focus: StudioFocus | null) => void;
};

const RevisionStudioContext = createContext<RevisionStudioContextValue | null>(null);

export function StudioRevisionProvider({ children }: { children: ReactNode }) {
  const [revising, setRevising] = useState<RevisionRequestedState | null>(null);
  const [completed, setCompleted] = useState<RevisionCompletedState | null>(null);

  const onDomainEvent = useCallback(
    (eventType: string, payload: Record<string, unknown>, focus: StudioFocus | null) => {
      if (eventType === "revision.requested") {
        const parsed = parseRevisionRequested(payload);
        if (!parsed) return;
        if (!subjectMatchesFocus(focus, parsed.subjectType, parsed.subjectId)) return;
        setRevising({ ...parsed, nextVersion: 0 });
        setCompleted(null);
        return;
      }
      if (eventType === "revision.completed") {
        const parsed = parseRevisionCompleted(payload);
        if (!parsed) return;
        if (
          !subjectMatchesFocus(focus, "", parsed.oldSubjectId) &&
          !subjectMatchesFocus(focus, "", parsed.newSubjectId)
        ) {
          return;
        }
        setRevising(null);
        setCompleted(parsed);
      }
    },
    [],
  );

  const clearCompleted = useCallback(() => setCompleted(null), []);

  const value = useMemo(
    () => ({ revising, completed, clearCompleted, onDomainEvent }),
    [revising, completed, clearCompleted, onDomainEvent],
  );

  return <RevisionStudioContext.Provider value={value}>{children}</RevisionStudioContext.Provider>;
}

export function useStudioRevision(): RevisionStudioContextValue {
  const ctx = useContext(RevisionStudioContext);
  if (!ctx) throw new Error("useStudioRevision requires StudioRevisionProvider");
  return ctx;
}
