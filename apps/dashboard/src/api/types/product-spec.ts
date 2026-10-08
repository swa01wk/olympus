export type ProductSpecGreenfieldProvenance = {
  kind: "greenfield";
  product_source_id: string | null;
  product_source_version: number | null;
  product_source_title: string | null;
  feature_source_refs: unknown[];
};

export type ProductSpecBrownfieldProvenance = {
  kind: "brownfield";
  confidence: string | null;
  recovered_evidence: {
    element_type: string;
    element_key: string;
    support_type: string;
    support_ref: string;
    strength: string;
  }[];
};

export type ProductSpecDocument = {
  project_id: string;
  capabilities: {
    id: string | null;
    key: string;
    name: string;
    description: string;
    features: {
      id: string;
      key: string;
      name: string;
      description: string;
      origin: string;
      source_refs: unknown[];
      spec: {
        id: string;
        version: number;
        status: string;
        spec_kind: string;
        body: {
          behavior: string;
          summary: string;
          rules: string[];
          inputs?: string[];
          outputs?: string[];
        };
        acceptance_criteria: {
          id: string;
          lineage_key: string;
          statement: string;
          given: string | null;
          when: string | null;
          then: string | null;
          mandatory: boolean;
        }[];
        provenance: ProductSpecGreenfieldProvenance | ProductSpecBrownfieldProvenance;
        known_gaps: { id: string; statement: string; confidence: string | null }[];
      };
    }[];
  }[];
};
