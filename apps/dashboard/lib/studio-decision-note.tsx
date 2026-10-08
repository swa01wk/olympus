"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  type ReactNode,
} from "react";

type DecisionNoteContextValue = {
  applyDraftNote: (approvalId: string, note: string) => void;
  registerDecisionPanel: (el: HTMLElement | null) => void;
  consumePendingNote: (pendingApprovalId: string) => string | null;
};

const DecisionNoteContext = createContext<DecisionNoteContextValue | null>(null);

export function StudioDecisionNoteProvider({ children }: { children: ReactNode }) {
  const panelRef = useRef<HTMLElement | null>(null);
  const pendingRef = useRef<{ approvalId: string; note: string } | null>(null);

  const registerDecisionPanel = useCallback((el: HTMLElement | null) => {
    panelRef.current = el;
  }, []);

  const applyDraftNote = useCallback((approvalId: string, note: string) => {
    pendingRef.current = { approvalId, note };
    panelRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, []);

  const consumePendingNote = useCallback((pendingApprovalId: string) => {
    const pending = pendingRef.current;
    if (!pending || pending.approvalId !== pendingApprovalId) return null;
    pendingRef.current = null;
    return pending.note;
  }, []);

  const value = useMemo(
    () => ({ applyDraftNote, registerDecisionPanel, consumePendingNote }),
    [applyDraftNote, registerDecisionPanel, consumePendingNote],
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
