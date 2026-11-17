import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NeedsYou } from "@/components/simple/NeedsYou";
import type { InboxItem } from "@/src/api/types/core";

const sendApprovalDecision = vi.fn().mockResolvedValue({});
const answerClarification = vi.fn().mockResolvedValue({});

vi.mock("@/src/api/commands", () => ({
  sendApprovalDecision: (...args: unknown[]) => sendApprovalDecision(...args),
  answerClarification: (...args: unknown[]) => answerClarification(...args),
}));

vi.mock("@/src/api/hooks/use-studio-queries", () => ({
  useFeatures: () => ({
    isLoading: false,
    data: [
      { id: "f1", name: "Create ticket", description: "Open a ticket" },
      { id: "f2", name: "List tickets", description: "" },
    ],
  }),
  useArchitectureDetail: () => ({ isLoading: false, data: null }),
}));

const scope: InboxItem = {
  kind: "APPROVAL",
  id: "inbox-1",
  title: "Scope approval",
  delivery_cycle_id: "c1",
  approval: {
    id: "apr-1",
    key: "APR-1",
    approval_type: "SCOPE",
    subject_type: "scope_set",
    subject_id: "s1",
    subject_hash: "h",
    status: "PENDING",
  },
};

const question: InboxItem = {
  kind: "CLARIFICATION",
  id: "inbox-2",
  title: "Question",
  delivery_cycle_id: "c1",
  clarification: { id: "cl-1", key: "CL-1", question: "Can closed tickets be reopened?", status: "OPEN" },
};

function renderNeedsYou(items: InboxItem[]) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <NeedsYou items={items} projectId="p1" inspectHref="/projects/p1/cycles/c1" />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  sendApprovalDecision.mockClear();
  answerClarification.mockClear();
});

describe("NeedsYou", () => {
  it("renders nothing when nothing is waiting", () => {
    const { container } = renderNeedsYou([]);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the features in plain language and approves", async () => {
    renderNeedsYou([scope]);
    expect(screen.getByText("Are these the right features?")).toBeInTheDocument();
    expect(screen.getByText("Create ticket")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(sendApprovalDecision).toHaveBeenCalledTimes(1));
    expect(sendApprovalDecision.mock.calls[0].slice(0, 3)).toEqual(["apr-1", "APPROVED", null]);
  });

  it("requires a note before requesting changes", async () => {
    renderNeedsYou([scope]);
    fireEvent.click(screen.getByRole("button", { name: "Request changes" }));
    fireEvent.click(screen.getByRole("button", { name: "Send feedback" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Tell Olympus what to change");
    expect(sendApprovalDecision).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("What should change?"), {
      target: { value: "Drop the list feature" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send feedback" }));
    await waitFor(() => expect(sendApprovalDecision).toHaveBeenCalledTimes(1));
    expect(sendApprovalDecision.mock.calls[0].slice(0, 3)).toEqual([
      "apr-1",
      "CHANGES_REQUESTED",
      "Drop the list feature",
    ]);
  });

  it("answers a question", async () => {
    renderNeedsYou([question]);
    expect(screen.getByText("Can closed tickets be reopened?")).toBeInTheDocument();
    const send = screen.getByRole("button", { name: "Send answer" });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Your answer"), { target: { value: "No" } });
    fireEvent.click(send);
    await waitFor(() => expect(answerClarification).toHaveBeenCalledWith("cl-1", "No"));
  });
});
