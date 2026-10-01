import { fid } from "../../engine/deterministic-id";
import type { Artifact } from "@/lib/contracts/entity-types";

/** Unified diff artifacts for candidate commits (fixture content). */
export function diffArtifactForCommit(
  sha: string,
  paths: string[],
  projectId: string,
): Artifact {
  const body = paths
    .map((p) => `--- a/${p}\n+++ b/${p}\n@@ -1,3 +1,4 @@\n+# fixture delta\n`)
    .join("\n");
  return {
    id: fid("artifact", `diff-${sha}`),
    project_id: projectId,
    kind: "UNIFIED_DIFF",
    schema_name: "text/x-diff",
    storage_ref: `logical:artifacts/diff-${sha.slice(0, 8)}`,
    size_bytes: body.length,
    content_hash: fid("hash", sha).replace(/-/g, "").slice(0, 64),
    created_at: "2025-09-15T10:00:00.000Z",
  };
}
