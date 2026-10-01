import type { ReleaseEligibilityEvaluation } from "@/lib/contracts/entity-types";

/** Renders server `eligible` only — no client-side eligibility math. */
export function EligibilityVerdict({ evaluation }: { evaluation: ReleaseEligibilityEvaluation }) {
  const verdict = evaluation.eligible ? "RELEASE ELIGIBLE" : "RELEASE BLOCKED";
  return (
    <div
      className={
        evaluation.eligible
          ? "rounded-lg border border-emerald-500/40 bg-emerald-500/10 p-4"
          : "rounded-lg border border-rose-500/40 bg-rose-500/10 p-4"
      }
    >
      <div className="text-sm font-semibold tracking-wide">{verdict}</div>
      <ul className="mt-3 space-y-2 text-sm">
        {[...evaluation.conditions]
          .sort((a, b) => Number(a.ok) - Number(b.ok))
          .map((c) => (
            <li key={c.name} className={c.ok ? "text-emerald-300" : "text-rose-300"}>
              <span className="font-mono text-xs">{c.name}</span>
              {!c.ok &&
                c.reasons.map((r) => (
                  <div key={r} className="ml-2 text-xs text-[var(--muted)]">
                    {r}
                  </div>
                ))}
            </li>
          ))}
      </ul>
    </div>
  );
}
