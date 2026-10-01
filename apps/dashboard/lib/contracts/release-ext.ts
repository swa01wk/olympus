import { z } from "zod";
import { Uuid } from "./common";

export const ReleaseManifestContent = z.object({
  manifest_hash: z.string(),
  integrated_sha: z.string(),
  integration_candidate_id: Uuid,
  integration_candidate_key: z.string().optional(),
  canonical_index_version_id: Uuid.nullable().optional(),
  canonical_index_key: z.string().optional(),
  baseline_set_id: Uuid.nullable().optional(),
  baseline_set_key: z.string().optional(),
  feature_spec_refs: z.array(z.string()).optional(),
  evidence_refs: z.array(z.string()).optional(),
});

export const ReleaseManifest = z.object({
  release_id: Uuid,
  content: ReleaseManifestContent,
});
