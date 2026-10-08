import type { CycleFinding } from "@/src/api/types/journey";

type CodeRef = { file_path?: string; line_start?: number | null };

export function findingCodeLocation(finding: CycleFinding): {
  file: string | null;
  line: number | null;
} {
  const refs = finding.detail.code_refs;
  if (Array.isArray(refs) && refs.length > 0) {
    const first = refs[0] as CodeRef;
    if (first?.file_path) {
      return { file: first.file_path, line: first.line_start ?? null };
    }
  }
  const file = finding.detail.file_path;
  if (typeof file === "string" && file) {
    const line = finding.detail.line_start ?? finding.detail.line;
    return {
      file,
      line: typeof line === "number" ? line : null,
    };
  }
  return { file: null, line: null };
}

export function findingBlockingLabel(finding: CycleFinding): string | null {
  if (!finding.blocking) return null;
  return "Blocking — must be resolved, remediated, or waived before release";
}
