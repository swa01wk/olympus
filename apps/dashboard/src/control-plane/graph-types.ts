import type { LaneId } from "@/src/control-plane/lanes";

export type GraphEdgeKind = "auth" | "inferred" | "obligation";

export type ControlPlaneGraphNode = {
  id: string;
  lane: LaneId;
  kind: string;
  ref: string;
  title: string;
  sub?: string;
  /** UI status key */
  status: string;
  backendStatus?: string;
  provenance?: string;
  confidence?: number;
  sha?: string;
  materialized: boolean;
  future?: boolean;
  /** Collapsed group */
  group?: boolean;
  groupCount?: number;
  memberIds?: string[];
  impact?: "direct" | "inferred" | "scope";
};

export type ControlPlaneGraphEdge = {
  id: string;
  from: string;
  to: string;
  rel: string;
  kind: GraphEdgeKind;
  confidence?: number;
};

export type ControlPlaneGraph = {
  nodes: ControlPlaneGraphNode[];
  edges: ControlPlaneGraphEdge[];
};

export type GraphRelation = {
  from: string;
  to: string;
  rel: string;
  kind?: GraphEdgeKind;
  confidence?: number;
  origin?: string;
};

export type BuildGraphInput = {
  cycle: { id: string; key: string; state: string; base_sha?: string | null };
  tasks: {
    id: string;
    key: string;
    title: string;
    status: string;
    blocked_reason?: string | null;
  }[];
  executions: {
    id: string;
    key: string;
    task_id: string;
    status: string;
    attempt_number?: number;
    snapshot_hash?: string | null;
  }[];
  integrationCandidates: {
    id: string;
    key: string;
    status: string;
    integrated_sha?: string | null;
    base_sha: string;
  }[];
  obligations?: { id: string; subject_key: string; status: string; required: boolean }[];
  relations?: GraphRelation[];
};
