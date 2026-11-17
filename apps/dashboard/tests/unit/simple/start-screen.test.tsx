import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StartScreen } from "@/components/simple/StartScreen";

const push = vi.fn();
const startJourney = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/src/api/autopilot", () => ({
  startJourney: (...args: unknown[]) => startJourney(...args),
}));

const PRD = "# SupportDesk — ticket API\n\nOperators open, list and close support tickets.";

function renderStart() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <StartScreen />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  push.mockClear();
  startJourney.mockReset();
});

describe("StartScreen", () => {
  it("needs a name and a real description before starting", () => {
    renderStart();
    const submit = screen.getByRole("button", { name: "Start building" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "SupportDesk" } });
    fireEvent.change(screen.getByLabelText("Product description (PRD)"), {
      target: { value: "short" },
    });
    expect(submit).toBeDisabled();
    expect(screen.getByText("Add a few sentences describing the app.")).toBeInTheDocument();
  });

  it("starts the run and opens it", async () => {
    startJourney.mockResolvedValue({ project_id: "p1", delivery_cycle_id: "c1", autopilot: {} });
    renderStart();
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "SupportDesk" } });
    fireEvent.change(screen.getByLabelText("Product description (PRD)"), {
      target: { value: PRD },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start building" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/runs/c1"));
    expect(startJourney.mock.calls[0][0]).toEqual({
      name: "SupportDesk",
      prd_title: "PRD",
      prd_text: PRD,
    });
  });

  it("shows the API error and stays on the page", async () => {
    const { OlympusApiError } = await import("@/src/api/errors");
    startJourney.mockRejectedValue(new OlympusApiError(400, "BAD", "Project key already exists"));
    renderStart();
    fireEvent.change(screen.getByLabelText("Project name"), { target: { value: "SupportDesk" } });
    fireEvent.change(screen.getByLabelText("Product description (PRD)"), {
      target: { value: PRD },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start building" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Project key already exists");
    expect(push).not.toHaveBeenCalled();
  });
});
