import Link from "next/link";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { EligibilityVerdict } from "@/components/release/EligibilityVerdict";
import type { ReleaseEligibilityEvaluation } from "@/lib/contracts/entity-types";

export function ReleaseReadiness({
  projectId,
  eligibility,
  release,
}: {
  projectId: string;
  eligibility: ReleaseEligibilityEvaluation | null;
  release: Record<string, unknown>;
}) {
  const eligible = release.eligible;

  return (
    <Panel
      title="Release Readiness"
      stateRail={eligibility?.eligible ? "complete" : eligibility ? "blocked" : "neutral"}
      actions={<FixtureBadge />}
    >
      {eligibility ? (
        <EligibilityVerdict evaluation={eligibility} />
      ) : (
        <p className="text-xs text-[var(--muted)]">
          Eligibility not evaluated for this cycle (404 NOT_EVALUATED).
          {eligible != null && (
            <span className="block font-mono text-[10px]">control_plane.release.eligible={String(eligible)}</span>
          )}
        </p>
      )}
      <Link href={`/projects/${projectId}/releases`} className="mt-2 inline-block text-xs text-amber-400 underline">
        Open releases
      </Link>
    </Panel>
  );
}
