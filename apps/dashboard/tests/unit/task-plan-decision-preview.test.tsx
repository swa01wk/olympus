import { cleanup, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TaskPlanDecisionPreview } from "@/components/studio/decision/TaskPlanDecisionPreview";

const fetchTaskPlan = vi.fn();

vi.mock("@/src/api/resources", async (importOriginal) => {
  const orig = await importOriginal<typeof import("@/src/api/resources")>();
  return { ...orig, fetchTaskPlan: (...args: unknown[]) => fetchTaskPlan(...args) };
});

const planBody = {
  tasks: [
    {
      ref: "T-1",
      title: "Add column delete guard",
      objective: "Refuse deleting a column that still has cards",
      work_type: "CODE_CHANGE",
      implementation_spec_ref: "IS-1",
      ac_refs: ["AC-COL-3"],
      allowed_scope: ["app/columns/service.py", "app/columns/routes.py"],
      constraints: [],
      required_outputs: ["code"],
      verification_requirements: ["unit"],
      estimated_size: "S",
    },
    {
      ref: "T-2",
      title: "Return 409 from the API",
      objective: "Map the guard to HTTP 409",
      work_type: "CODE_CHANGE",
      implementation_spec_ref: "IS-1",
      ac_refs: ["AC-COL-3"],
      allowed_scope: ["app/columns/routes.py"],
      constraints: [],
      required_outputs: ["code"],
      verification_requirements: ["api"],
      estimated_size: "M",
    },
  ],
  dependencies: [{ task_ref: "T-2", depends_on_ref: "T-1", reason: "route uses the guard" }],
  risks: [
    { description: "Clients relying on cascade delete break", severity: "HIGH", related_refs: ["T-2"] },
  ],
  open_questions: [],
};

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  fetchTaskPlan.mockReset();
});

describe("TaskPlanDecisionPreview", () => {
  it("renders task refs, sizes, scopes, dependency edges and plan risks", async () => {
    fetchTaskPlan.mockResolvedValue({
      id: "plan-1",
      status: "PROPOSED",
      body: planBody,
      validation_report: null,
    });
    wrap(<TaskPlanDecisionPreview planId="plan-1" />);

    expect(await screen.findByText("Tasks (2)")).toBeTruthy();
    expect(fetchTaskPlan).toHaveBeenCalledWith("plan-1");
    expect(screen.getByText("size S")).toBeTruthy();
    expect(screen.getByText("size M")).toBeTruthy();
    expect(
      screen.getByText("scope: app/columns/service.py, app/columns/routes.py"),
    ).toBeTruthy();
    expect(screen.getByText("scope: app/columns/routes.py")).toBeTruthy();
    expect(screen.getAllByText("Add column delete guard").length).toBeGreaterThan(0);

    const deps = screen.getByRole("list", { name: "Task dependencies" });
    expect(within(deps).getByText("T-1 → T-2")).toBeTruthy();
    expect(within(deps).getByText(/route uses the guard/)).toBeTruthy();

    expect(screen.getByText("Risks (1)")).toBeTruthy();
    expect(screen.getByText("HIGH")).toBeTruthy();
    expect(screen.getByText(/Clients relying on cascade delete break/)).toBeTruthy();
    expect(screen.queryByText(/standalone Accept/i)).toBeNull();
  });

  it("states when there are no dependencies or risks", async () => {
    fetchTaskPlan.mockResolvedValue({
      id: "plan-2",
      status: "PROPOSED",
      body: { tasks: [planBody.tasks[0]], dependencies: [], risks: [] },
      validation_report: null,
    });
    wrap(<TaskPlanDecisionPreview planId="plan-2" />);
    expect(await screen.findByText(/No dependencies/)).toBeTruthy();
    expect(screen.getByText("No plan-level risks recorded.")).toBeTruthy();
  });
});
