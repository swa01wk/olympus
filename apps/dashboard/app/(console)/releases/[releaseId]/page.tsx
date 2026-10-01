"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { EligibilityVerdict } from "@/components/release/EligibilityVerdict";
import { StatusBadge } from "@/components/status/StatusBadge";
import { getServices } from "@/lib/api/services";
import { qk } from "@/lib/query/keys";
import { Sha } from "@/components/design/Sha";

export default function ReleasePage() {
  const { releaseId } = useParams<{ releaseId: string }>();
  const releaseQ = useQuery({
    queryKey: qk.release(releaseId),
    queryFn: async () => (await getServices()).release.get(releaseId),
  });
  const eligQ = useQuery({
    queryKey: qk.releaseEligibility(releaseQ.data?.delivery_cycle_id ?? ""),
    queryFn: async () =>
      (await getServices()).release.eligibility(releaseQ.data!.delivery_cycle_id),
    enabled: !!releaseQ.data,
  });

  const r = releaseQ.data;
  if (!r) return <p>Loading…</p>;

  return (
    <div className="space-y-4">
      <h1 className="font-mono text-xl font-semibold">Release {r.key}</h1>
      <StatusBadge value={r.status} />
      <p className="font-mono text-sm">
        integrated_sha:{" "}
        <span data-testid={`release-${r.key}`}>
          <Sha sha={r.integrated_sha} role="manifest" />
        </span>
      </p>
      {eligQ.data && <EligibilityVerdict evaluation={eligQ.data} />}
      {r.status === "NOT_ELIGIBLE" && (
        <p className="text-xs text-[var(--muted)]">Approve disabled until server reports ELIGIBLE.</p>
      )}
    </div>
  );
}
