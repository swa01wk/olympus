import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RevisionNoteDraftCard } from "@/components/studio/chat/RevisionNoteDraftCard";
import { StudioDecisionNoteProvider, useStudioDecisionNote } from "@/lib/studio-decision-note";
import type { ReactNode } from "react";

const sendApprovalDecision = vi.fn();

vi.mock("@/src/api/commands", () => ({
  sendApprovalDecision,
}));

const noteApi = {
  current: null as ReturnType<typeof useStudioDecisionNote> | null,
};

function Wrapper({ children }: { children: ReactNode }) {
  noteApi.current = useStudioDecisionNote();
  return children;
}

afterEach(() => {
  cleanup();
  sendApprovalDecision.mockClear();
  noteApi.current = null;
});

describe("RevisionNoteDraftCard", () => {
  it("fills decision note without submitting approval", () => {
    render(
      <StudioDecisionNoteProvider>
        <Wrapper>
          <RevisionNoteDraftCard
            draft={{ approval_id: "apr-9", note: "Tighten acceptance criteria" }}
          />
        </Wrapper>
      </StudioDecisionNoteProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Use in decision panel" }));
    expect(noteApi.current?.consumePendingNote("apr-9")).toBe("Tighten acceptance criteria");
    expect(sendApprovalDecision).not.toHaveBeenCalled();
  });
});
