"use client";

import { StudioDecisionNoteProvider } from "@/lib/studio-decision-note";
import { StudioFocusProvider } from "@/lib/studio-focus";
import { StudioRevisionProvider } from "@/lib/studio-revision";
import type { ReactNode } from "react";

export function StudioProviders({ children }: { children: ReactNode }) {
  return (
    <StudioFocusProvider>
      <StudioDecisionNoteProvider>
        <StudioRevisionProvider>{children}</StudioRevisionProvider>
      </StudioDecisionNoteProvider>
    </StudioFocusProvider>
  );
}
