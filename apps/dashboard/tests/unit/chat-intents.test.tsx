import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatTurnView } from "@/components/studio/chat/ChatTurnView";
import { ProposalCard } from "@/components/studio/chat/ProposalCard";

const ctx = { projectId: "p1", cycleId: "c1", cycleState: "DISCOVERY" };

afterEach(() => {
  cleanup();
});

describe("ChatTurnView intents", () => {
  it("renders EXPLAIN with record link", () => {
    render(
      <ChatTurnView
        turn={{ role: "assistant", text: "See TASK-104 for detail.", intent: "EXPLAIN" }}
        ctx={ctx}
        studioBasePath="/projects/p1/cycles/c1/studio"
        clarifications={[]}
        onDismissProposal={() => {}}
        onSelectStage={vi.fn()}
      />,
    );
    expect(screen.getByRole("link", { name: "TASK-104" })).toBeTruthy();
  });

  it("renders OUT_OF_SCOPE muted", () => {
    const { container } = render(
      <ChatTurnView
        turn={{ role: "assistant", text: "Outside scope.", intent: "OUT_OF_SCOPE" }}
        ctx={ctx}
        studioBasePath="/studio"
        clarifications={[]}
        onDismissProposal={() => {}}
        onSelectStage={vi.fn()}
      />,
    );
    expect(container.querySelector(".ol-muted")?.textContent).toContain("Outside scope");
  });

  it("renders NAVIGATE as plain text", () => {
    render(
      <ChatTurnView
        turn={{ role: "assistant", text: "Open planning view.", intent: "NAVIGATE" }}
        ctx={ctx}
        studioBasePath="/studio"
        clarifications={[]}
        onDismissProposal={() => {}}
        onSelectStage={vi.fn()}
      />,
    );
    expect(screen.getByText("Open planning view.")).toBeTruthy();
  });

  it("renders PROPOSE_COMMAND card", () => {
    render(
      <ChatTurnView
        turn={{
          role: "assistant",
          text: "I can decompose.",
          intent: "PROPOSE_COMMAND",
          proposal: {
            command: "decompose_source",
            target_ref: "src-1",
            args: { source_id: "src-1" },
            rationale: "Run decomposition",
          },
        }}
        ctx={ctx}
        studioBasePath="/projects/p1/cycles/c1/studio"
        clarifications={[]}
        onDismissProposal={() => {}}
        onSelectStage={vi.fn()}
      />,
    );
    expect(screen.getByText(/Proposed command/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Run" })).toBeTruthy();
  });

  it("renders ANSWER_CLARIFICATION draft card", () => {
    render(
      <ChatTurnView
        turn={{
          role: "assistant",
          text: "Draft answer",
          intent: "ANSWER_CLARIFICATION",
          clarification_answer_draft: { clarification_id: "cl-1", answer: "Draft" },
        }}
        ctx={ctx}
        studioBasePath="/studio"
        clarifications={[
          { id: "cl-1", key: "CL-1", question: "Which API?", status: "OPEN", answer: null },
        ]}
        onDismissProposal={() => {}}
        onSelectStage={vi.fn()}
      />,
    );
    expect(screen.getByText("Which API?")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send answer" })).toBeTruthy();
  });
});

describe("ProposalCard approval.decide", () => {
  it("never calls fetch on Run", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ProposalCard
        proposal={{
          command: "approval.decide",
          target_ref: "APR-1",
          args: {},
          rationale: "Approve",
        }}
        ctx={ctx}
        studioHref="/studio"
        onDismiss={() => {}}
      />,
    );
    expect(screen.getByText(/Not runnable from chat/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Run" })).toBeNull();
    fireEvent.click(screen.getByRole("link", { name: /Open in workspace/i }));
    expect(fetchMock).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
