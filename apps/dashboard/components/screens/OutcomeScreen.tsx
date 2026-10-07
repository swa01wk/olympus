"use client";

import { EligibilityChecklist } from "@/components/assurance/EligibilityChecklist";
import { CycleDrillFrame } from "@/components/cycle/CycleDrillFrame";
import { EmptyState, KV, Panel, StatusBadge } from "@/components/primitives";
import {
  useCycleOutcome,
  useProjectReleases,
  useReleaseEligibility,
} from "@/src/api/hooks/use-drill-queries";
import { useDeliveryCycle } from "@/src/api/hooks/use-olympus-queries";
import { isApiError } from "@/src/api/client";

export function OutcomeScreen({ projectId, cycleId }: { projectId: string; cycleId: string }) {
  const cycle = useDeliveryCycle(cycleId);
  const eligibility = useReleaseEligibility(cycleId);
  const outcome = useCycleOutcome(cycleId);
  const releases = useProjectReleases(projectId);
  const cycleReleases = (releases.data ?? []).filter((r) => r.delivery_cycle_id === cycleId);

  const isBrownfield = cycle.data?.type === "BROWNFIELD_ONBOARDING";
  const readyForChange = cycle.data?.state === "READY";

  return (
    <CycleDrillFrame projectId={projectId} cycleId={cycleId} activeScreen="S10">
      <Panel title="S10 · Release / outcome" sub="Eligibility, approvals, and recorded outcome">
        {isBrownfield ? (
          <div className="text-sm mb-4">
            <p className="ol-muted">Brownfield handoff — no release execute until change journeys.</p>
            <p className="mt-2">
              Start Feature Change or Bug Fix when{" "}
              <StatusBadge status={readyForChange ? "READY" : cycle.data?.state ?? "—"} /> at READY_FOR_CHANGE.
            </p>
          </div>
        ) : (
          eligibility.data && (
            <EligibilityChecklist
              eligible={eligibility.data.eligible}
              conditions={eligibility.data.conditions}
            />
          )
        )}
        <div className="mt-4">
          <h3 className="ol-insp-st">Releases for this cycle</h3>
          {cycleReleases.length === 0 && (
            <p className="text-sm ol-muted">No release records yet.</p>
          )}
          <ul className="text-sm flex flex-col gap-2">
            {cycleReleases.map((r) => (
              <li key={r.id} className="border border-[var(--border)] p-2 rounded">
                <span className="font-mono">{r.key}</span> — <StatusBadge status={r.status} />{" "}
                <span className="font-mono text-xs">{r.integrated_sha.slice(0, 10)}</span>
              </li>
            ))}
          </ul>
        </div>
        {outcome.isError && isApiError(outcome.error) && outcome.error.status === 404 ? (
          <EmptyState title="No delivery outcome" description="Outcome is recorded when the cycle completes." />
        ) : outcome.data ? (
          <Panel title="Delivery outcome" sub={outcome.data.result}>
            <KV rows={[["Result", outcome.data.result]]} />
            <pre className="text-xs mt-2 overflow-auto">{JSON.stringify(outcome.data.content, null, 2)}</pre>
          </Panel>
        ) : null}
      </Panel>
    </CycleDrillFrame>
  );
}
