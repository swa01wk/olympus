import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ArchitectureVersionEditor } from "@/components/studio/editors/ArchitectureVersionEditor";
import { ImplementationSpecVersionEditor } from "@/components/studio/editors/ImplementationSpecVersionEditor";
import { OlympusApiError } from "@/src/api/errors";
import type { ArchitectureView } from "@/src/api/types/product-model";

const postArchitectureVersion = vi.fn();
const postImplementationSpecVersion = vi.fn();

vi.mock("@/src/api/commands", () => ({
  postArchitectureVersion: (...args: unknown[]) => postArchitectureVersion(...args),
  postImplementationSpecVersion: (...args: unknown[]) => postImplementationSpecVersion(...args),
}));

const architectureBody = {
  summary: "Layered Kanban service",
  technology_stack: { language: "python", web: "fastapi", orm: "sqlalchemy", tests: "pytest" },
  components: [
    { name: "columns", layer: "domain", responsibility: "Column lifecycle", directory: "app/columns" },
  ],
  layers: ["api", "domain"],
  dependency_rules: ["api -> domain"],
  directory_conventions: [{ path: "app/", purpose: "application code" }],
  decisions: [{ id: "D-1", title: "REST", decision: "Use REST", rationale: "Simple clients" }],
  constraints: ["No cascading deletes"],
  risks: [],
};

const architecture: ArchitectureView = {
  id: "arch-1",
  version: 2,
  status: "PROPOSED",
  kind: "GREENFIELD",
  body: architectureBody,
  contracts: [
    {
      key: "API-COLUMNS",
      kind: "API",
      name: "Columns API",
      definition: { method: "DELETE", path: "/columns/{id}", description: "Delete a column" },
    },
  ],
};

const specBody = {
  summary: "Guard column deletion",
  components: ["columns"],
  apis: [{ method: "DELETE", path: "/columns/{id}", contract_key: "API-COLUMNS" }],
  schemas: [],
  data_changes: [],
  integration_points: [],
  required_tests: [],
  file_scope: ["app/columns/service.py"],
  architecture_refs: ["D-1"],
  ac_coverage: [],
};

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  postArchitectureVersion.mockReset();
  postImplementationSpecVersion.mockReset();
});

describe("ArchitectureVersionEditor", () => {
  it("saves form edits as the body, omits unchanged contracts, and shows the v→v+1 diff", async () => {
    postArchitectureVersion.mockResolvedValue({ id: "arch-2", version: 3, status: "PROPOSED" });
    wrap(<ArchitectureVersionEditor architecture={architecture} projectId="p1" cycleId="cyc-1" />);

    fireEvent.change(screen.getByLabelText("Summary"), { target: { value: "Layered Kanban API" } });
    fireEvent.change(screen.getByLabelText("component 1 Name"), { target: { value: "boards" } });
    fireEvent.click(screen.getByRole("button", { name: "Add dependency rule" }));
    fireEvent.change(screen.getByLabelText("dependency rule 2"), {
      target: { value: "domain -> nothing" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Remove constraint 1" }));
    fireEvent.change(screen.getByLabelText("Note"), { target: { value: "tighten rules" } });
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }));

    await waitFor(() => expect(postArchitectureVersion).toHaveBeenCalledTimes(1));
    const [id, payload] = postArchitectureVersion.mock.calls[0]!;
    expect(id).toBe("arch-1");
    expect(payload).toEqual({
      body: {
        ...architectureBody,
        summary: "Layered Kanban API",
        components: [{ ...architectureBody.components[0], name: "boards" }],
        dependency_rules: ["api -> domain", "domain -> nothing"],
        constraints: [],
      },
      note: "tighten rules",
      delivery_cycle_id: "cyc-1",
    });
    expect("contracts" in payload).toBe(false);

    const status = await screen.findByRole("status");
    expect(within(status).getByText("Saved v2 → v3")).toBeTruthy();
    expect(within(status).getByText(/fresh approval for v3 is pending/i)).toBeTruthy();
    const diff = within(status).getByLabelText("Diff v2 → v3");
    expect(diff.textContent).toMatch(/\+\s+"summary": "Layered Kanban API"/);
    expect(diff.textContent).toMatch(/-\s+"summary": "Layered Kanban service"/);
  });

  it("sends the full contract list when contracts are edited", async () => {
    postArchitectureVersion.mockResolvedValue({ id: "arch-2", version: 3, status: "PROPOSED" });
    wrap(<ArchitectureVersionEditor architecture={architecture} projectId="p1" cycleId="cyc-1" />);

    fireEvent.change(screen.getByLabelText("contract 1 Path"), {
      target: { value: "/columns/{column_id}" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add contract" }));
    fireEvent.change(screen.getByLabelText("contract 2 Key"), { target: { value: "EVT-COL" } });
    fireEvent.change(screen.getByLabelText("contract 2 Kind"), { target: { value: "EVENT" } });
    fireEvent.change(screen.getByLabelText("contract 2 Name"), { target: { value: "Column deleted" } });
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }));

    await waitFor(() => expect(postArchitectureVersion).toHaveBeenCalledTimes(1));
    expect(postArchitectureVersion.mock.calls[0]![1].contracts).toEqual([
      {
        key: "API-COLUMNS",
        kind: "API",
        name: "Columns API",
        method: "DELETE",
        path: "/columns/{column_id}",
        description: "Delete a column",
      },
      { key: "EVT-COL", kind: "EVENT", name: "Column deleted", method: "", path: "", description: "" },
    ]);
  });

  it("renders 422 validation errors as a list", async () => {
    postArchitectureVersion.mockRejectedValue(
      new OlympusApiError(422, "HTTP_ERROR", "Unprocessable Entity", {
        errors: ["components.0.name: Field required", "layers: Input should be a valid list"],
      }),
    );
    wrap(<ArchitectureVersionEditor architecture={architecture} projectId="p1" cycleId="cyc-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }));

    const alert = await screen.findByRole("alert");
    const items = within(alert).getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual(["components.0.name: Field required", "layers: Input should be a valid list"]);
    expect(alert.textContent).not.toContain("{");
  });

  it("toggles to raw JSON, saves edits from it, and carries them back to the form", async () => {
    postArchitectureVersion.mockResolvedValue({ id: "arch-2", version: 3, status: "PROPOSED" });
    wrap(<ArchitectureVersionEditor architecture={architecture} projectId="p1" cycleId="cyc-1" />);

    fireEvent.click(screen.getByRole("button", { name: "Raw JSON" }));
    const raw = screen.getByLabelText("Body (JSON)") as HTMLTextAreaElement;
    const parsed = JSON.parse(raw.value) as { body: Record<string, unknown>; contracts: unknown[] };
    expect(parsed.body.summary).toBe("Layered Kanban service");
    expect(parsed.contracts).toHaveLength(1);

    fireEvent.change(raw, { target: { value: "{ not json" } });
    fireEvent.click(screen.getByRole("button", { name: "Form" }));
    expect(within(screen.getByRole("alert")).getByText(/Invalid JSON/)).toBeTruthy();

    fireEvent.change(raw, {
      target: { value: JSON.stringify({ body: { ...architectureBody, summary: "From raw" } }) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Form" }));
    expect((screen.getByLabelText("Summary") as HTMLTextAreaElement).value).toBe("From raw");

    fireEvent.click(screen.getByRole("button", { name: "Raw JSON" }));
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }));
    await waitFor(() => expect(postArchitectureVersion).toHaveBeenCalledTimes(1));
    const payload = postArchitectureVersion.mock.calls[0]![1];
    expect(payload.body.summary).toBe("From raw");
    expect("contracts" in payload).toBe(false);
  });
});

describe("ImplementationSpecVersionEditor", () => {
  it("saves form edits as the body and reports the new spec id", async () => {
    postImplementationSpecVersion.mockResolvedValue({ id: "spec-2", version: 2, status: "PROPOSED" });
    const onSaved = vi.fn();
    wrap(
      <ImplementationSpecVersionEditor
        title="Edit implementation spec (F-1)"
        spec={{ id: "spec-1", version: 1, body: specBody }}
        featureId="feat-1"
        cycleId="cyc-1"
        onSaved={onSaved}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Add file scope entry" }));
    fireEvent.change(screen.getByLabelText("file scope entry 2"), {
      target: { value: "app/columns/routes.py" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add required test" }));
    fireEvent.change(screen.getByLabelText("required test 1 Kind"), { target: { value: "api" } });
    fireEvent.change(screen.getByLabelText("required test 1 AC keys (comma-separated)"), {
      target: { value: "AC-COL-3, AC-COL-4" },
    });
    fireEvent.change(screen.getByLabelText("required test 1 Description"), {
      target: { value: "DELETE returns 409" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }));

    await waitFor(() => expect(postImplementationSpecVersion).toHaveBeenCalledTimes(1));
    expect(postImplementationSpecVersion).toHaveBeenCalledWith("spec-1", {
      body: {
        ...specBody,
        file_scope: ["app/columns/service.py", "app/columns/routes.py"],
        required_tests: [
          { kind: "api", ac_keys: ["AC-COL-3", "AC-COL-4"], description: "DELETE returns 409" },
        ],
      },
      note: undefined,
      delivery_cycle_id: "cyc-1",
    });
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith("spec-2"));
    expect(screen.getByText("Saved v1 → v2")).toBeTruthy();
  });

  it("renders conformance violations as a list", async () => {
    postImplementationSpecVersion.mockRejectedValue(
      new OlympusApiError(422, "HTTP_ERROR", "Unprocessable Entity", {
        violations: ["component 'billing' is not in the architecture"],
        conformance_report: { ok: false, violations: ["component 'billing' is not in the architecture"] },
      }),
    );
    wrap(
      <ImplementationSpecVersionEditor
        title="Edit implementation spec (F-1)"
        spec={{ id: "spec-1", version: 1, body: specBody }}
        featureId="feat-1"
        cycleId="cyc-1"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
      "component 'billing' is not in the architecture",
    ]);
    expect(alert.textContent).not.toContain("conformance_report");
  });

  it("saves a raw JSON body", async () => {
    postImplementationSpecVersion.mockResolvedValue({ id: "spec-2", version: 2, status: "PROPOSED" });
    wrap(
      <ImplementationSpecVersionEditor
        title="Edit implementation spec (F-1)"
        spec={{ id: "spec-1", version: 1, body: specBody }}
        featureId="feat-1"
        cycleId="cyc-1"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Raw JSON" }));
    fireEvent.change(screen.getByLabelText("Body (JSON)"), {
      target: { value: JSON.stringify({ ...specBody, summary: "Raw summary" }) },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save as new version" }));
    await waitFor(() => expect(postImplementationSpecVersion).toHaveBeenCalledTimes(1));
    expect(postImplementationSpecVersion.mock.calls[0]![1].body.summary).toBe("Raw summary");
  });
});
