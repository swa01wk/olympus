import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RevisionNoteDraftCard } from "@/components/studio/chat/RevisionNoteDraftCard";
import { StudioDecisionNoteProvider, useStudioDecisionNote } from "@/lib/studio-decision-note";
import { useEffect, useState } from "react";

const sendApprovalDecision = vi.fn();

vi.mock("@/src/api/commands", () => ({
  sendApprovalDecision,
}));

function PanelProbe({ approvalId }: { approvalId: string }) {
  const { registerDecisionPanel, peekPendingNote, clearPendingNote } = useStudioDecisionNote();
  const [note, setNote] = useState(() => peekPendingNote(approvalId) ?? "");
  useEffect(() => {
    clearPendingNote(approvalId);
    return registerDecisionPanel({ approvalId, element: null, applyNote: setNote });
  }, [approvalId, registerDecisionPanel, clearPendingNote]);
  return <output aria-label="panel note">{note}</output>;
}

function Harness({ panelMounted }: { panelMounted: boolean }) {
  return (
    <StudioDecisionNoteProvider>
      <RevisionNoteDraftCard
        draft={{ approval_id: "apr-9", note: "Tighten acceptance criteria" }}
      />
      {panelMounted && <PanelProbe approvalId="apr-9" />}
    </StudioDecisionNoteProvider>
  );
}

afterEach(() => {
  cleanup();
  sendApprovalDecision.mockClear();
});

describe("RevisionNoteDraftCard", () => {
  it("fills an already-mounted decision panel without submitting approval", () => {
    render(<Harness panelMounted />);
    fireEvent.click(screen.getByRole("button", { name: "Use in decision panel" }));
    expect(screen.getByLabelText("panel note").textContent).toBe("Tighten acceptance criteria");
    expect(sendApprovalDecision).not.toHaveBeenCalled();
  });

  it("hands the note to a decision panel that mounts later", () => {
    const { rerender } = render(<Harness panelMounted={false} />);
    fireEvent.click(screen.getByRole("button", { name: "Use in decision panel" }));
    rerender(<Harness panelMounted />);
    expect(screen.getByLabelText("panel note").textContent).toBe("Tighten acceptance criteria");
    expect(sendApprovalDecision).not.toHaveBeenCalled();
  });
});
