import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProductSpecView } from "@/components/studio/ProductSpecView";

vi.mock("@/src/api/resources", () => ({
  getProductSpec: vi.fn().mockResolvedValue({
    project_id: "p1",
    capabilities: [
      {
        id: "c1",
        key: "CAP",
        name: "Tickets",
        description: "",
        features: [
          {
            id: "f1",
            key: "FEAT",
            name: "Archive project",
            description: "",
            origin: "GREENFIELD",
            source_refs: [],
            spec: {
              id: "s1",
              version: 1,
              status: "APPROVED",
              spec_kind: "CANONICAL",
              body: { behavior: "Beh", summary: "Sum", rules: ["Rule one"] },
              acceptance_criteria: [],
              provenance: {
                kind: "greenfield",
                product_source_id: null,
                product_source_version: 2,
                product_source_title: "PRD",
                feature_source_refs: [],
              },
              known_gaps: [],
            },
          },
          {
            id: "f2",
            key: "FEAT2",
            name: "Move card",
            description: "",
            origin: "RECOVERED",
            source_refs: [],
            spec: {
              id: "s2",
              version: 1,
              status: "APPROVED",
              spec_kind: "CANONICAL",
              body: { behavior: "Drag", summary: "Move", rules: [] },
              acceptance_criteria: [],
              provenance: {
                kind: "brownfield",
                confidence: "HIGH",
                recovered_evidence: [
                  {
                    support_ref: "tests/test_cards.py::test_move_card",
                    strength: "HIGH",
                    element_type: "AC",
                    element_key: "AC-1",
                    support_type: "TEST",
                  },
                ],
              },
              known_gaps: [{ id: "g1", statement: "Edge unverified", confidence: null }],
            },
          },
        ],
      },
    ],
  }),
  getSourceContent: vi.fn(),
}));

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => cleanup());

describe("ProductSpecView", () => {
  it("renders greenfield and brownfield provenance chips", async () => {
    wrap(<ProductSpecView projectId="p1" />);
    expect(await screen.findByRole("heading", { name: /Move card/ })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /PRD v2 · Feature: Archive project/ }).length).toBeGreaterThan(0);
    expect(screen.getByText(/HIGH · tests\/test_cards.py::test_move_card/)).toBeTruthy();
    expect(screen.getByText(/Known gap: not confirmed/)).toBeTruthy();
  });
});
