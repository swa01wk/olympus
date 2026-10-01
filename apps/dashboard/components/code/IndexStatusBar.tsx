import { FixtureBadge } from "@/components/states/FixtureBadge";
import type { CodeIndexVersion } from "@/lib/contracts/entity-types";

export function IndexStatusBar({
  canonical,
  integratedSha,
}: {
  canonical: CodeIndexVersion | null;
  integratedSha?: string | null;
}) {
  const match =
    canonical?.commit_sha && integratedSha
      ? canonical.commit_sha === integratedSha
      : null;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded border border-[var(--border)] bg-[var(--raised)] px-3 py-2 text-xs">
      <FixtureBadge />
      {canonical ? (
        <>
          <span>
            Canonical index @ <span className="font-mono">{canonical.commit_sha.slice(0, 12)}</span>
          </span>
          <span className="text-[var(--muted)]">kind {canonical.kind}</span>
          {match != null && (
            <span className={match ? "text-emerald-300" : "text-orange-300"}>
              pointer SHA {match ? "==" : "≠"} current IC integrated_sha
            </span>
          )}
        </>
      ) : (
        <span className="text-[var(--muted)]">No canonical index</span>
      )}
    </div>
  );
}
