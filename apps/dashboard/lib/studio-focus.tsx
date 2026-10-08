"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type StudioFocus = {
  subject_type: string;
  subject_id: string;
};

type StudioFocusContextValue = {
  focus: StudioFocus | null;
  setFocus: (next: StudioFocus | null) => void;
};

const StudioFocusContext = createContext<StudioFocusContextValue | null>(null);

export function StudioFocusProvider({ children }: { children: ReactNode }) {
  const [focus, setFocusState] = useState<StudioFocus | null>(null);
  const setFocus = useCallback((next: StudioFocus | null) => {
    setFocusState(next);
  }, []);
  const value = useMemo(() => ({ focus, setFocus }), [focus, setFocus]);
  return <StudioFocusContext.Provider value={value}>{children}</StudioFocusContext.Provider>;
}

export function useStudioFocus(): StudioFocus | null {
  return useContext(StudioFocusContext)?.focus ?? null;
}

/** Stage views register the magnified subject while mounted. */
export function useRegisterStudioFocus(next: StudioFocus | null | undefined) {
  const ctx = useContext(StudioFocusContext);
  const subjectType = next?.subject_type;
  const subjectId = next?.subject_id;
  const setFocus = ctx?.setFocus;
  useEffect(() => {
    if (!setFocus) return;
    if (subjectType && subjectId) {
      setFocus({ subject_type: subjectType, subject_id: subjectId });
    } else {
      setFocus(null);
    }
    return () => setFocus(null);
  }, [setFocus, subjectType, subjectId]);
}
