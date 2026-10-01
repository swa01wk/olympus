import type {
  Defect,
  Reproduction,
  RootCauseAnalysis,
  TraceCorrelation,
} from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

const now = "2025-09-15T12:00:00.000Z";

export function buildDefect() {
  const defect: Defect = {
    id: IDS.defect004,
    project_id: IDS.project,
    delivery_cycle_id: IDS.dc004,
    key: "DEF-004",
    title: "Closed ticket update returns HTTP 500",
    status: "IN_ASSURANCE",
    severity: "HIGH",
  };

  const reproductions: Reproduction[] = [
    {
      id: "11111111-1111-4111-8111-111111113201",
      defect_id: IDS.defect004,
      phase: "PRE_FIX",
      status: "CONFIRMED",
      steps: [
        "Create ticket T-100",
        "Transition T-100 to CLOSED",
        "PATCH /tickets/T-100 with {status: OPEN}",
      ],
      observed_at: now,
    },
    {
      id: "11111111-1111-4111-8111-111111113202",
      defect_id: IDS.defect004,
      phase: "POST_FIX",
      status: "PENDING",
      steps: [
        "Deploy IC-004 integrated SHA",
        "Repeat closed-ticket PATCH",
        "Expect HTTP 409 Conflict",
      ],
    },
  ];

  const trace: TraceCorrelation = {
    id: "11111111-1111-4111-8111-111111113203",
    defect_id: IDS.defect004,
    delivery_cycle_id: IDS.dc004,
    candidates: [
      {
        stable_key: "supportdesk::app/services/ticket_service.py::TicketService.update_status",
        evidence_basis: "STACK_TRACE",
        path: [
          "HTTP PATCH /tickets/{id}",
          "TicketRouter.update_ticket",
          "TicketService.update_status",
        ],
      },
      {
        stable_key: "supportdesk::app/api/tickets.py::update_ticket",
        evidence_basis: "REQUEST_LOG",
        path: ["HTTP PATCH /tickets/{id}", "update_ticket"],
      },
    ],
  };

  const rca: RootCauseAnalysis = {
    id: "11111111-1111-4111-8111-111111113204",
    defect_id: IDS.defect004,
    knowledge_class: "INFERENCE",
    summary: "Closed-state guard raised uncaught exception instead of domain conflict",
    contributing_factors: [
      "Missing 409 mapping in exception handler",
      "No regression test for closed-ticket update",
    ],
  };

  return { defect, reproductions, trace, rca };
}
