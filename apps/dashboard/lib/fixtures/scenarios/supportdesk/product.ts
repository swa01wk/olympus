import type {
  AcceptanceCriterion,
  Capability,
  Feature,
  FeatureSpec,
  ProductSource,
} from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

export function buildProduct() {
  const productSources: ProductSource[] = [
    {
      id: IDS.productSourcePrd,
      project_id: IDS.project,
      key: "PRD-SUPPORTDESK",
      title: "SupportDesk Product Requirements",
      source_kind: "PRD",
      version: 1,
    },
  ];

  const capabilities: Capability[] = [
    {
      id: IDS.capabilityTickets,
      project_id: IDS.project,
      key: "CAP-TICKETS",
      title: "Ticket management",
    },
  ];

  const features: Feature[] = [
    {
      id: IDS.featureTicketMgmt,
      project_id: IDS.project,
      capability_id: IDS.capabilityTickets,
      key: "FEAT-TICKETS",
      title: "Ticket lifecycle",
    },
  ];

  const featureSpecs: FeatureSpec[] = [
    {
      id: IDS.fs014,
      feature_id: IDS.featureTicketMgmt,
      key: "FS-014",
      version: 2,
      status: "APPROVED",
      title: "Ticket priority (LOW, MEDIUM, HIGH)",
      knowledge_class: "DECISION",
    },
    {
      id: "11111111-1111-4111-8111-111111112103",
      feature_id: IDS.featureTicketMgmt,
      key: "FS-001",
      version: 1,
      status: "APPROVED",
      title: "Core ticket CRUD",
      knowledge_class: "FACT",
    },
  ];

  const acceptanceCriteria: AcceptanceCriterion[] = [
    {
      id: IDS.ac00402,
      feature_spec_id: "11111111-1111-4111-8111-111111112105",
      key: "AC-004-02",
      statement: "Updating a closed ticket returns HTTP 409, not 500",
      version: 1,
    },
    {
      id: "11111111-1111-4111-8111-111111112106",
      feature_spec_id: IDS.fs014,
      key: "AC-014-01",
      statement: "Tickets expose priority enum LOW|MEDIUM|HIGH",
      version: 1,
    },
  ];

  return { productSources, capabilities, features, featureSpecs, acceptanceCriteria };
}
