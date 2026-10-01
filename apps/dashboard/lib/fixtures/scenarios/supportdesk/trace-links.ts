import type { LineageGraph, SpecCodeLink } from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

export function buildTraceLinks() {
  const specCodeLinks: SpecCodeLink[] = [
    {
      id: "11111111-1111-4111-8111-111111114101",
      index_version_id: IDS.idxCanonicalR1,
      spec_type: "FEATURE_SPEC",
      spec_id: "11111111-1111-4111-8111-111111112103",
      spec_version: 1,
      entity_stable_key: "supportdesk::IC-001::class-5",
      relation: "IMPLEMENTS",
      origin: "GENERATED_LINEAGE",
      confidence: 1,
      status: "ACTIVE",
    },
    {
      id: "11111111-1111-4111-8111-111111114102",
      index_version_id: IDS.idxCanonicalR1,
      spec_type: "IMPLEMENTATION_SPEC",
      spec_id: IDS.ia003,
      spec_version: 1,
      entity_stable_key: "supportdesk::EX-551::method-7",
      relation: "IMPLEMENTS",
      origin: "DISCOVERED",
      confidence: 0.68,
      status: "ACTIVE",
    },
    {
      id: "11111111-1111-4111-8111-111111114103",
      index_version_id: IDS.idxCanonicalIc004,
      spec_type: "ACCEPTANCE_CRITERION",
      spec_id: IDS.ac00402,
      spec_version: 1,
      entity_stable_key:
        "supportdesk::app/services/ticket_service.py::TicketService.update_status",
      relation: "VERIFIES",
      origin: "HUMAN_CONFIRMED",
      confidence: 0.95,
      status: "ACTIVE",
    },
  ];

  const sampleLineage: LineageGraph = {
    root_type: "CODE_ENTITY",
    root_id: "11111111-1111-4111-8111-000000000005",
    direction: "REVERSE",
    nodes: [
      {
        type: "CODE_ENTITY",
        id: "11111111-1111-4111-8111-000000000005",
        label: "TicketService.update_status",
      },
      {
        type: "ACCEPTANCE_CRITERION",
        id: IDS.ac00402,
        key: "AC-004-02",
        version: 1,
        label: "Closed ticket returns 409",
        origin: "HUMAN_CONFIRMED",
      },
      {
        type: "FEATURE_SPEC",
        id: "11111111-1111-4111-8111-111111112105",
        key: "FS-BUG-004",
        version: 1,
        label: "Closed ticket update behavior",
      },
    ],
    edges: [
      {
        from: IDS.ac00402,
        to: "11111111-1111-4111-8111-000000000005",
        relation: "VERIFIES",
        origin: "HUMAN_CONFIRMED",
      },
      {
        from: "11111111-1111-4111-8111-111111112105",
        to: IDS.ac00402,
        relation: "CONTAINS",
      },
    ],
  };

  return { specCodeLinks, sampleLineage };
}
