import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DiscoveryStage } from "@/components/studio/workspace/DiscoveryStage";
import { StageWorkspace } from "@/components/studio/workspace/StageWorkspace";
import { UnsupportedStage } from "@/components/studio/workspace/UnsupportedStage";
import type { DeliveryCycle } from "@/src/api/types/core";

vi.mock("@/src/api/hooks/use-studio-queries", () => ({
  useSources: () => ({
    data: [
      {
        id: "src-1",
        version: 1,
        title: "SupportDesk PRD",
        lineage_key: "default",
        content_hash: "abc",
      },
    ],
    isLoading: false,
    isError: false,
  }),
  useSourceContent: () => ({
    data: { title: "PRD", text: "# Hello", mime_type: "text/markdown" },
    isLoading: false,
    isError: false,
  }),
  useDecompositions: () => ({
    data: [{ id: "dec-1", status: "ACCEPTED", execution_id: null, validation_report: null }],
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/src/api/hooks/use-studio-mutations", () => ({
  useUploadProductSource: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDecomposeSource: () => ({ isPending: false }),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const greenfieldCycle: DeliveryCycle = {
  id: "cyc-1",
  project_id: "proj-1",
  key: "GF-001",
  type: "GREENFIELD_BUILD",
  objective: "Build",
  state: "DISCOVERY",
  state_version: 1,
  repository_id: null,
  base_sha: null,
  allowed_commands: [],
};

afterEach(() => cleanup());

describe("StageWorkspace", () => {
  it("routes GREENFIELD DISCOVERY to discovery view", () => {
    wrap(
      <StageWorkspace
        projectId="proj-1"
        cycle={greenfieldCycle}
        stage="DISCOVERY"
        inbox={[]}
      />,
    );
    expect(screen.getByText(/SupportDesk PRD/i)).toBeTruthy();
    expect(screen.getByText(/# Hello/)).toBeTruthy();
  });

});

describe("DiscoveryStage", () => {
  it("lists sources and decomposition status from fixtures", () => {
    wrap(<DiscoveryStage projectId="proj-1" cycleId="cyc-1" />);
    expect(screen.getByRole("button", { name: /v1/i })).toBeTruthy();
    expect(screen.getByText(/ACCEPTED/i)).toBeTruthy();
  });
});

describe("UnsupportedStage", () => {
  it("names cycle type and stage", () => {
    render(<UnsupportedStage cycleType="FEATURE_CHANGE" stage="SPEC_DELTA" />);
    expect(screen.getByText(/FEATURE_CHANGE · SPEC_DELTA/)).toBeTruthy();
  });
});
