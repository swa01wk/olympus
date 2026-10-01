import type {
  ChangeRequest,
  ConnectorAction,
  ConnectorConfig,
  InboundEvent,
} from "@/lib/contracts/entity-types";
import { IDS } from "./ids";

const now = "2025-09-15T12:00:00.000Z";

export function buildIntegrations() {
  const connectors: ConnectorConfig[] = [
    {
      id: "11111111-1111-4111-8111-111111113301",
      project_id: IDS.project,
      connector_type: "git_local",
      name: "SupportDesk local git",
      status: "HEALTHY",
    },
    {
      id: "11111111-1111-4111-8111-111111113302",
      project_id: IDS.project,
      connector_type: "gitea",
      name: "SupportDesk Gitea",
      status: "HEALTHY",
    },
  ];

  const inboundEvents: InboundEvent[] = [
    {
      id: "11111111-1111-4111-8111-111111113401",
      project_id: IDS.project,
      source: "gitea",
      event_type: "issues.opened",
      status: "PROCESSED",
      received_at: now,
      correlation_id: "corr-inbound-cr003",
    },
  ];

  const connectorActions: ConnectorAction[] = [
    {
      id: "11111111-1111-4111-8111-111111113501",
      connector_id: "11111111-1111-4111-8111-111111113302",
      action_type: "comment_issue",
      status: "SUCCEEDED",
      idempotency_key: "gitea-comment-cr003-1",
      correlation_id: "corr-inbound-cr003",
    },
  ];

  const changeRequests: ChangeRequest[] = [
    {
      id: IDS.cr003,
      project_id: IDS.project,
      delivery_cycle_id: IDS.dc003,
      key: "CR-003",
      title: "Add ticket priority: LOW, MEDIUM, HIGH",
      source: "GITEA_ISSUE",
      status: "IN_PROGRESS",
    },
  ];

  return { connectors, inboundEvents, connectorActions, changeRequests };
}
