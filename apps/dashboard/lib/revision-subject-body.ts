import { apiRequest } from "@/src/api/client";
import { getFeatureSpec } from "@/src/api/resources";

export async function fetchRevisionSubjectBody(
  subjectType: string,
  subjectId: string,
): Promise<unknown> {
  const t = subjectType.toLowerCase();
  if (t === "architecture") {
    const row = await apiRequest<{ body: unknown }>(`/architectures/${subjectId}`);
    return row.body;
  }
  if (t === "feature_spec") {
    const row = await getFeatureSpec(subjectId);
    return row.body;
  }
  if (t === "implementation_spec") {
    const row = await apiRequest<{ body: unknown }>(`/implementation-specs/${subjectId}`);
    return row.body;
  }
  if (t === "spec_delta") {
    const row = await apiRequest<{ changes: unknown }>(`/spec-deltas/${subjectId}`);
    return row.changes;
  }
  return {};
}
