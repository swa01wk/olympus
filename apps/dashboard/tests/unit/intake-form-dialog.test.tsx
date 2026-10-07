import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { IntakeFormDialog } from "@/components/dialogs/IntakeFormDialog";

const putSecret = vi.fn();
const registerRepository = vi.fn();
const createDeliveryCycleCommand = vi.fn();

vi.mock("@/src/api/commands", () => ({
  putSecret: (...args: unknown[]) => putSecret(...args),
  registerRepository: (...args: unknown[]) => registerRepository(...args),
  createDeliveryCycleCommand: (...args: unknown[]) => createDeliveryCycleCommand(...args),
  retryMaterialization: vi.fn(),
}));

let materializationStatus: "CLONING" | "READY" = "CLONING";
let activeRepoId: string | null = null;

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useProject: () => ({
    data: {
      id: "proj-1",
      key: "PRJ",
      name: "Demo",
      description: null,
      readiness_state: "READY",
    },
  }),
}));

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useProjectRepositories: () => ({ data: [] }),
  useRepository: (repositoryId: string | undefined) => {
    if (!repositoryId || repositoryId !== activeRepoId) {
      return { data: undefined, isLoading: false };
    }
    return {
      data: {
        id: repositoryId,
        status: materializationStatus,
        name: "app",
        provider: "GITHUB",
        remote_url: "https://github.com/org/app.git",
        default_branch: "main",
        project_id: "proj-1",
        source_type: "EXTERNAL_CLONE",
        registered_sha: materializationStatus === "READY" ? "abc" : null,
        canonical_commit: materializationStatus === "READY" ? "abc" : null,
        released_commit: null,
        status_reason: null,
        credential_ref: "secret:ref",
        credential_status: "OK",
        workspace: null,
      },
      isLoading: false,
    };
  },
  useRepositoryMaterializations: () => ({ data: [] }),
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>) };
}

function inputAfterLabel(label: string): HTMLInputElement {
  const span = screen.getByText(label);
  const field = span.closest("label");
  const input = field?.querySelector("input, textarea");
  if (!input) throw new Error(`No input for label ${label}`);
  return input as HTMLInputElement;
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  materializationStatus = "CLONING";
  activeRepoId = null;
});

describe("IntakeFormDialog brownfield", () => {
  it("register → materializing → READY → create cycle without token in query cache", async () => {
    putSecret.mockResolvedValue({ credential_ref: "secret:ref" });
    registerRepository.mockImplementation(async () => {
      activeRepoId = "repo-new";
      materializationStatus = "CLONING";
      return { id: "repo-new", status: "CLONING" };
    });
    createDeliveryCycleCommand.mockResolvedValue({ id: "cycle-bf" });

    const { client, rerender } = wrap(
      <IntakeFormDialog open projectId="proj-1" onClose={() => {}} />,
    );

    fireEvent.click(screen.getByRole("radio", { name: "Brownfield Onboarding" }));
    fireEvent.click(screen.getByRole("radio", { name: "Register new" }));

    fireEvent.change(inputAfterLabel("Name"), { target: { value: "app" } });
    fireEvent.change(inputAfterLabel("Remote URL"), {
      target: { value: "https://github.com/org/app.git" },
    });
    fireEvent.change(inputAfterLabel("Access token (optional, sent once)"), {
      target: { value: "ghp_super_secret_token" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Register repository" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm send" }));

    await waitFor(() => expect(registerRepository).toHaveBeenCalled());
    expect(putSecret).toHaveBeenCalledWith(
      "repo-PRJ-app",
      "ghp_super_secret_token",
      expect.any(String),
    );

    rerender(
      <QueryClientProvider client={client}>
        <IntakeFormDialog open projectId="proj-1" onClose={() => {}} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("CLONING")).toBeTruthy();

    materializationStatus = "READY";
    rerender(
      <QueryClientProvider client={client}>
        <IntakeFormDialog open projectId="proj-1" onClose={() => {}} />
      </QueryClientProvider>,
    );

    const cacheJson = JSON.stringify(client.getQueryCache().getAll());
    expect(cacheJson).not.toContain("ghp_super_secret_token");

    fireEvent.change(inputAfterLabel("Objective"), {
      target: { value: "Baseline the monolith" },
    });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Create delivery cycle" })).toHaveProperty(
        "disabled",
        false,
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: "Create delivery cycle" }));

    await waitFor(() =>
      expect(createDeliveryCycleCommand).toHaveBeenCalledWith(
        "proj-1",
        "BROWNFIELD_ONBOARDING",
        "Baseline the monolith",
        "repo-new",
        expect.any(String),
      ),
    );
    expect(push).toHaveBeenCalledWith("/projects/proj-1/cycles/cycle-bf/studio");
  });
});
