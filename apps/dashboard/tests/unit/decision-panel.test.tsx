import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DecisionPanel } from "@/components/studio/DecisionPanel";
import { RevisionNoteDraftCard } from "@/components/studio/chat/RevisionNoteDraftCard";
import { StudioDecisionNoteProvider } from "@/lib/studio-decision-note";
import type { InboxItem, TransitionPreview } from "@/src/api/types/core";
import type { ArchitectureView } from "@/src/api/types/product-model";

let projectArchitecture: ArchitectureView | null = null;

vi.mock("@/src/api/hooks/use-olympus-queries", () => ({
  useActorMe: () => ({ data: { roles: ["OPERATOR"] } }),
}));

vi.mock("@/src/api/hooks/use-studio-queries", () => ({
  useApprovalDetail: () => ({
    data: {
      id: "apr-1",
      key: "APR-007",
      approval_type: "SCOPE",
      subject_type: "ScopeBundle",
      subject_id: "sub-1",
      subject_version: 2,
      subject_hash: "abc123",
      status: "PENDING",
      project_id: "p1",
      delivery_cycle_id: "c1",
    },
  }),
  useFeatureSpecDetail: () => ({ data: null }),
  useProjectArchitecture: () => ({ data: projectArchitecture }),
  useReleaseManifest: () => ({ data: null }),
}));

vi.mock("@/src/api/resources", async (importOriginal) => {
  const orig = await importOriginal<typeof import("@/src/api/resources")>();
  return {
    ...orig,
    fetchAuditForTarget: vi.fn().mockResolvedValue([]),
  };
});

const inbox: InboxItem[] = [
  {
    kind: "APPROVAL",
    id: "inbox-1",
    title: "Scope",
    approval: {
      id: "apr-1",
      key: "APR-007",
      approval_type: "SCOPE",
      subject_type: "ScopeBundle",
      subject_id: "sub-1",
      subject_hash: "abc123",
      status: "PENDING",
    },
  },
];

const transitions: TransitionPreview[] = [
  {
    command: "start_architecture",
    to_state: "ARCHITECTURE",
    target_state: "ARCHITECTURE",
    allowed: false,
    guard_preview: [],
    guard_results: [{ guard_id: "scope_approved", ok: false, reasons: ["Pending SCOPE"] }],
    authorization_denied: false,
  },
];

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  projectArchitecture = null;
});

function approvalInbox(approvalType: string, subjectId = "sub-1"): InboxItem[] {
  return [
    {
      kind: "APPROVAL",
      id: `inbox-${approvalType}`,
      title: approvalType,
      approval: {
        id: `apr-${approvalType}`,
        key: `APR-${approvalType}`,
        approval_type: approvalType,
        subject_type: "x",
        subject_id: subjectId,
        subject_hash: "hash",
        status: "PENDING",
      },
    },
  ];
}

describe("DecisionPanel", () => {
  it("shows read-only APPROVER message for OPERATOR-only actor", () => {
    wrap(
      <DecisionPanel
        stage="PRODUCT_MODEL"
        cycleType="GREENFIELD_BUILD"
        cycleState="PRODUCT_MODEL"
        inbox={inbox}
        projectId="p1"
        nextTransitions={transitions}
        onDecided={() => {}}
      />,
    );
    expect(screen.getByText(/Decision required/i)).toBeTruthy();
    expect(screen.getByText(/APPROVER role/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Approve" })).toHaveProperty("disabled", true);
    expect(screen.getByText(/agent will revise using your note/i)).toBeTruthy();
  });

  it("fills the note from a chat revision draft while already open", () => {
    wrap(
      <StudioDecisionNoteProvider>
        <DecisionPanel
          stage="PRODUCT_MODEL"
          cycleType="GREENFIELD_BUILD"
          cycleState="PRODUCT_MODEL"
          inbox={inbox}
          projectId="p1"
          nextTransitions={transitions}
          onDecided={() => {}}
        />
        <RevisionNoteDraftCard draft={{ approval_id: "apr-1", note: "Split the guard" }} />
      </StudioDecisionNoteProvider>,
    );
    const note = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(note.value).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Use in decision panel" }));
    expect(note.value).toBe("Split the guard");
  });

  it("hidden when no pending approval for stage", () => {
    const { container } = wrap(
      <DecisionPanel
        stage="DISCOVERY"
        cycleType="GREENFIELD_BUILD"
        cycleState="PRODUCT_MODEL"
        inbox={inbox}
        projectId="p1"
        nextTransitions={transitions}
        onDecided={() => {}}
      />,
    );
    expect(container.textContent).toBe("");
  });

  it("shows repair IMPLEMENTATION_SPEC at ROOT_CAUSE on bug fix cycles", () => {
    wrap(
      <DecisionPanel
        stage="ROOT_CAUSE"
        cycleType="BUG_FIX"
        cycleState="ROOT_CAUSE"
        inbox={[
          {
            kind: "APPROVAL",
            id: "inbox-rc",
            title: "Repair spec",
            approval: {
              id: "apr-rc",
              key: "APR-RC",
              approval_type: "IMPLEMENTATION_SPEC",
              subject_type: "ImplementationSpec",
              subject_id: "spec-1",
              subject_hash: "hash",
              status: "PENDING",
            },
          },
        ]}
        projectId="p1"
        nextTransitions={[]}
        onDecided={() => {}}
      />,
    );
    expect(screen.getByText(/Decision required/i)).toBeTruthy();
    expect(screen.getByText(/IMPLEMENTATION_SPEC · APR-RC/)).toBeTruthy();
  });

  it("shows ARCHITECTURE_DELTA at IMPACT_ANALYSIS on feature change cycles", () => {
    wrap(
      <DecisionPanel
        stage="IMPACT_ANALYSIS"
        cycleType="FEATURE_CHANGE"
        cycleState="IMPACT_ANALYSIS"
        inbox={[
          {
            kind: "APPROVAL",
            id: "inbox-ad",
            title: "Architecture delta",
            approval: {
              id: "apr-ad",
              key: "APR-AD",
              approval_type: "ARCHITECTURE_DELTA",
              subject_type: "Architecture",
              subject_id: "arch-1",
              subject_hash: "hash",
              status: "PENDING",
            },
          },
        ]}
        projectId="p1"
        nextTransitions={[]}
        onDecided={() => {}}
      />,
    );
    expect(screen.getByText(/Decision required/i)).toBeTruthy();
    expect(screen.getByText(/ARCHITECTURE_DELTA · APR-AD/)).toBeTruthy();
  });

  it("says no agent revises EXPECTED_BEHAVIOR", () => {
    wrap(
      <DecisionPanel
        stage="EXPECTED_BEHAVIOR"
        cycleType="BUG_FIX"
        cycleState="EXPECTED_BEHAVIOR"
        inbox={approvalInbox("EXPECTED_BEHAVIOR")}
        projectId="p1"
        nextTransitions={[]}
        onDecided={() => {}}
      />,
    );
    expect(screen.getByText(/no agent revises this item/i)).toBeTruthy();
    expect(screen.queryByText(/until revision support ships/i)).toBeNull();
  });

  it("says no agent revises SCOPE once the cycle left PRODUCT_MODEL", () => {
    wrap(
      <DecisionPanel
        stage="PRODUCT_MODEL"
        cycleType="GREENFIELD_BUILD"
        cycleState="ARCHITECTURE"
        inbox={inbox}
        projectId="p1"
        nextTransitions={[]}
        onDecided={() => {}}
      />,
    );
    expect(screen.getByText(/no agent revises this item/i)).toBeTruthy();
  });

  it("uses the architecture kind: ARCHITECTURE approval on a DELTA subject is not revised", () => {
    projectArchitecture = {
      id: "arch-d",
      version: 2,
      status: "PROPOSED",
      kind: "DELTA",
      body: {},
      contracts: [],
    };
    wrap(
      <DecisionPanel
        stage="ARCHITECTURE"
        cycleType="GREENFIELD_BUILD"
        cycleState="ARCHITECTURE"
        inbox={approvalInbox("ARCHITECTURE", "arch-d")}
        projectId="p1"
        nextTransitions={[]}
        onDecided={() => {}}
      />,
    );
    expect(screen.getByText(/no agent revises this item/i)).toBeTruthy();
  });
});
