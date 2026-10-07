import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StageWorkspace } from "@/components/studio/workspace/StageWorkspace";
import { SpecDeltaStage } from "@/components/studio/workspace/journeys/SpecDeltaStage";
import { BugFixStage } from "@/components/studio/workspace/journeys/BugFixStage";
import { FeatureChangeIntakeStage } from "@/components/studio/workspace/journeys/FeatureChangeIntakeStage";
import type { DeliveryCycle } from "@/src/api/types/core";

vi.mock("@/src/api/hooks/use-journey-queries", () => ({
  useCycleSpecDelta: () => ({
    data: { id: "d1", status: "PROPOSED", content_hash: "abc", changes: [{ op: "add" }] },
    isLoading: false,
    isError: false,
  }),
  useChangeRequests: () => ({
    data: [{ id: "cr1", key: "CR-1", status: "OPEN", delivery_cycle_id: "cyc-fc", title: "Dark mode" }],
    isLoading: false,
  }),
  useChangeInterpretation: () => ({ data: { status: "OK", candidates: [], interpretation: {} }, isLoading: false }),
  useDefects: () => ({
    data: [
      {
        id: "def-1",
        key: "DEF-1",
        status: "TRIAGE",
        delivery_cycle_id: "cyc-bf",
        title: "Login fails",
        severity: "HIGH",
      },
    ],
    isLoading: false,
  }),
  useDefectDetail: () => ({
    data: {
      id: "def-1",
      key: "DEF-1",
      status: "TRIAGE",
      title: "Login fails",
      description: "500 on submit",
      triage: { severity: "HIGH" },
      linked_feature_ids: [],
      expected_ac_ids: [],
      affected_sha: null,
      delivery_cycle_id: "cyc-bf",
    },
    isLoading: false,
  }),
  useDefectReproductions: () => ({ data: [], isLoading: false }),
  useDefectRootCause: () => ({ data: null, isLoading: false }),
  useBrownfieldDiscovery: () => ({
    data: {
      id: "disc-1",
      repository_id: "repo-1",
      delivery_cycle_id: "cyc-bf",
      commit_sha: "sha1",
      content_hash: "hash1",
      content: { modules: 3 },
    },
    isLoading: false,
    isError: false,
  }),
  useRecoveryProposals: () => ({ data: { proposals: [] }, isLoading: false }),
  useReviewQueue: () => ({ data: [], isLoading: false }),
  useReadinessAssessment: () => ({ data: null, isLoading: false }),
  useObservedBehaviors: () => ({ data: [], isLoading: false }),
}));

vi.mock("@/src/api/hooks/use-drill-queries", () => ({
  useProjectRepositoryView: () => ({ data: { repository: { name: "app", status: "ACTIVE" } }, isLoading: false }),
  useLatestImpact: () => ({ data: null, isLoading: false, isError: true }),
}));

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useProjectOverview: () => ({ data: null }),
  useDeliveryCycle: () => ({ data: null }),
  useIntegrationCandidates: () => ({ data: [] }),
}));

const base: DeliveryCycle = {
  id: "cyc-fc",
  project_id: "proj-1",
  key: "FC-1",
  type: "FEATURE_CHANGE",
  objective: "Change",
  state: "INTAKE",
  state_version: 1,
  repository_id: null,
  base_sha: null,
  allowed_commands: [],
};

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => cleanup());

describe("journey stage views", () => {
  it("SpecDeltaStage renders delta fixture", () => {
    wrap(<SpecDeltaStage cycleId="cyc-fc" />);
    expect(screen.getByText(/PROPOSED/i)).toBeTruthy();
  });

  it("FeatureChangeIntakeStage lists change request", () => {
    wrap(<FeatureChangeIntakeStage projectId="proj-1" cycleId="cyc-fc" />);
    expect(screen.getByText(/Dark mode/i)).toBeTruthy();
  });

  it("BugFixStage triage shows defect", () => {
    wrap(<BugFixStage projectId="proj-1" cycleId="cyc-bf" stage="TRIAGE" />);
    expect(screen.getByText(/Login fails/i)).toBeTruthy();
  });

  it("StageWorkspace brownfield RECON is not unknown stage", () => {
    wrap(
      <StageWorkspace
        projectId="proj-1"
        cycle={{ ...base, id: "cyc-bf", type: "BROWNFIELD_ONBOARDING", state: "RECON" }}
        stage="RECON"
        inbox={[]}
      />,
    );
    expect(screen.queryByText(/Unknown stage/i)).toBeNull();
    expect(screen.getByText(/Repository discovery/i)).toBeTruthy();
  });

  it("StageWorkspace feature change SPEC_DELTA route", () => {
    wrap(
      <StageWorkspace
        projectId="proj-1"
        cycle={{ ...base, state: "SPEC_DELTA" }}
        stage="SPEC_DELTA"
        inbox={[]}
      />,
    );
    expect(screen.getByText(/Spec delta/i)).toBeTruthy();
  });
});
