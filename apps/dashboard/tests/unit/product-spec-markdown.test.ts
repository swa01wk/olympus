import { describe, expect, it } from "vitest";
import { productSpecToMarkdown } from "@/lib/product-spec-markdown";
import type { ProductSpecDocument } from "@/src/api/types/product-spec";

const sample: ProductSpecDocument = {
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
            body: {
              behavior: "Archive closes work",
              summary: "Archive",
              rules: ["Only admins archive"],
            },
            acceptance_criteria: [
              {
                id: "ac1",
                lineage_key: "AC-1",
                statement: "Archived hidden",
                given: "project open",
                when: "admin archives",
                then: "project hidden",
                mandatory: true,
              },
            ],
            provenance: {
              kind: "greenfield",
              product_source_id: "src-1",
              product_source_version: 2,
              product_source_title: "PRD",
              feature_source_refs: [],
            },
            known_gaps: [{ id: "g1", statement: "Retention policy unknown", confidence: null }],
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
                  element_type: "AC",
                  element_key: "AC-1",
                  support_type: "TEST",
                  support_ref: "tests/test_cards.py::test_move_card",
                  strength: "HIGH",
                },
              ],
            },
            known_gaps: [],
          },
        },
      ],
    },
  ],
};

describe("productSpecToMarkdown", () => {
  it("matches snapshot for greenfield and brownfield provenance", () => {
    expect(productSpecToMarkdown(sample)).toMatchInlineSnapshot(`
      "# Product specification

      ## Tickets

      ### Archive project

      **Behavior**
      Archive closes work

      **Rules**
      - Only admins archive [PRD v2 · PRD]

      **Acceptance criteria**
      - Archived hidden (Given project open · When admin archives · Then project hidden) [mandatory] [PRD v2 · PRD]

      > Known gap: not confirmed — Retention policy unknown

      ### Move card

      **Behavior**
      Drag
      "
    `);
  });
});
