import type { ImpactAssessment } from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

export function buildImpact() {
  const impactAssessments: ImpactAssessment[] = [
    {
      id: IDS.impact003,
      delivery_cycle_id: IDS.dc003,
      change_request_id: IDS.cr003,
      feature_spec_id: IDS.fs014,
      status: "APPROVED",
      items: [
        {
          id: "11111111-1111-4111-8111-111111112901",
          stable_key: "supportdesk::app/models/ticket.py::Ticket",
          kind: "DIRECT",
          path: [
            { from: "FS-014@v2", relation: "DELTA", to: "app/models/ticket.py" },
            { from: "app/models/ticket.py", relation: "CONTAINS", to: "Ticket" },
          ],
        },
        {
          id: "11111111-1111-4111-8111-111111112902",
          stable_key: "supportdesk::app/api/tickets.py::update_ticket",
          kind: "TRANSITIVE",
          path: [
            { from: "FS-014@v2", relation: "DELTA", to: "app/api/tickets.py" },
            { from: "app/api/tickets.py", relation: "CONTAINS", to: "update_ticket" },
          ],
        },
        {
          id: "11111111-1111-4111-8111-111111112903",
          stable_key: "supportdesk::tests/acceptance/test_ticket_priority.py",
          kind: "CANDIDATE",
          path: [{ from: "FS-014@v2", relation: "SUGGESTS_TEST", to: "test_ticket_priority.py" }],
        },
      ],
    },
  ];

  return { impactAssessments };
}
