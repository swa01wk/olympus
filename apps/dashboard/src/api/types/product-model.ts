/** Matches `core.product_model.schemas.FeatureSpecBody`. */
export type FeatureSpecBody = {
  behavior: string;
  summary: string;
  inputs: string[];
  outputs: string[];
  rules: string[];
  constraints?: string[];
  out_of_scope?: string[];
};

export type ProductSourceSummary = {
  id: string;
  version: number;
  title: string;
  lineage_key: string;
  content_hash: string;
};

export type ProductSourceContent = {
  title: string;
  text: string;
  mime_type: string;
};

export type ProductDecompositionSummary = {
  id: string;
  status: string;
  execution_id: string | null;
  validation_report: unknown;
};

export type Capability = {
  id: string;
  key: string;
  name: string;
  status: string;
};

export type Feature = {
  id: string;
  key: string;
  name: string;
  status: string;
  capability_id: string | null;
};

export type FeatureSpecSummary = {
  id: string;
  version: number;
  status: string;
  lineage_key: string;
};

/** `GET /specs/{spec_id}` — body fields match FeatureSpecBody plus metadata. */
export type FeatureSpecDetail = {
  id: string;
  version: number;
  status: string;
  spec_kind: string;
  body: FeatureSpecBody;
};

export type Clarification = {
  id: string;
  key: string;
  question: string;
  status: string;
  answer: string | null;
};

export type ArchitectureView = {
  id: string;
  version: number;
  status: string;
  body: Record<string, unknown>;
  contracts: {
    key: string;
    kind: string;
    name: string;
    definition: Record<string, unknown>;
  }[];
};

export type ImplementationSpecSummary = {
  id: string;
  lineage_key: string;
  version: number;
  status: string;
};
