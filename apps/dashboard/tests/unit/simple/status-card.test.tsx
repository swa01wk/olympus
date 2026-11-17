import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StatusCard } from "@/components/simple/RunScreen";
import type { AutopilotView } from "@/src/api/types/autopilot";
import type { DeliveryCycle } from "@/src/api/types/core";

const retryAutopilot = vi.fn();
const setAutopilot = vi.fn();

vi.mock("@/src/api/autopilot", () => ({
  retryAutopilot: (...a: unknown[]) => retryAutopilot(...a),
  setAutopilot: (...a: unknown[]) => setAutopilot(...a),
  fetchAutopilot: vi.fn(),
  fetchAutopilotActivity: vi.fn(),
  fetchHome: vi.fn(),
  startJourney: vi.fn(),
}));

const cycle = { id: "c1", project_id: "p1", type: "GREENFIELD_BUILD", state: "PLANNING" } as DeliveryCycle;

function view(over: Partial<AutopilotView>): AutopilotView {
  return {
    delivery_cycle_id: "c1",
    supported: true,
    enabled: true,
    status: "WORKING",
    step: "specs",
    message: "Writing a detailed plan for each feature (1 of 4 done)",
    detail: { done: 1, total: 4 },
    last_error: null,
    updated_at: null,
    code_path: null,
    ...over,
  };
}

function renderCard(v: AutopilotView) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <StatusCard view={v} cycle={cycle} inspectHref="/inspect" />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  retryAutopilot.mockReset();
  setAutopilot.mockReset();
});

describe("StatusCard", () => {
  it("shows progress while working and lets the person pause", async () => {
    setAutopilot.mockResolvedValue(view({ status: "OFF", enabled: false }));
    renderCard(view({}));
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    await waitFor(() => expect(setAutopilot).toHaveBeenCalledWith("c1", false));
  });

  it("offers Try again only for a retryable stop", async () => {
    retryAutopilot.mockResolvedValue(view({}));
    renderCard(
      view({
        status: "BLOCKED",
        message: "Breaking down the PRD failed: model provider unavailable",
        detail: { retryable: true },
      }),
    );
    expect(screen.getByText("Stopped")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(retryAutopilot).toHaveBeenCalledWith("c1"));
  });

  it("does not offer a retry when it would not help", () => {
    renderCard(view({ status: "BLOCKED", message: "Merging the code failed.", detail: {} }));
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect(screen.getByRole("link", { name: "Details" })).toHaveAttribute("href", "/inspect");
  });

  it("explains journeys Autopilot does not drive yet", () => {
    renderCard(view({ status: "OFF", enabled: false, supported: false }));
    expect(screen.getByText("This kind of run isn’t automated yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Turn Autopilot on" })).toBeNull();
  });
});
