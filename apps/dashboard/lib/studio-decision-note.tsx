"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

export type DecisionPanelHandle = {
  approvalId: string;
  element: HTMLElement | null;
  applyNote: (note: string) => void;
};

type DecisionNoteContextValue = {
  applyDraftNote: (approvalId: string, note: string) => void;
  /** Returns an unregister function. */
  registerDecisionPanel: (handle: DecisionPanelHandle) => () => void;
  /** Read-only so it is safe inside a lazy state initializer. */
  peekPendingNote: (approvalId: string) => string | null;
  clearPendingNote: (approvalId: string) => void;
};

const DecisionNoteContext = createContext<DecisionNoteContextValue | null>(null);

export function StudioDecisionNoteProvider({ children }: { children: ReactNode }) {
  const panelRef = useRef<DecisionPanelHandle | null>(null);
  const pendingRef = useRef<{ approvalId: string; note: string } | null>(null);

  const registerDecisionPanel = useCallback((handle: DecisionPanelHandle) => {
    panelRef.current = handle;
    return () => {
      if (panelRef.current === handle) panelRef.current = null;
    };
  }, []);

  const applyDraftNote = useCallback((approvalId: string, note: string) => {
    const panel = panelRef.current;
    if (panel?.approvalId === approvalId) {
      pendingRef.current = null;
      panel.applyNote(note);
    } else {
      pendingRef.current = { approvalId, note };
    }
    panel?.element?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, []);

  const peekPendingNote = useCallback((approvalId: string) => {
    const pending = pendingRef.current;
    return pending?.approvalId === approvalId ? pending.note : null;
  }, []);

  const clearPendingNote = useCallback((approvalId: string) => {
    if (pendingRef.current?.approvalId === approvalId) pendingRef.current = null;
  }, []);

  const value = useMemo(
    () => ({ applyDraftNote, registerDecisionPanel, peekPendingNote, clearPendingNote }),
    [applyDraftNote, registerDecisionPanel, peekPendingNote, clearPendingNote],
  );

  return <DecisionNoteContext.Provider value={value}>{children}</DecisionNoteContext.Provider>;
}

export function useStudioDecisionNoteOptional(): DecisionNoteContextValue | null {
  return useContext(DecisionNoteContext);
}

export function useStudioDecisionNote(): DecisionNoteContextValue {
  const ctx = useStudioDecisionNoteOptional();
  if (!ctx) {
    throw new Error("useStudioDecisionNote requires StudioDecisionNoteProvider");
  }
  return ctx;
}
