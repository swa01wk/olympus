import { ReasonCode } from "@/components/control-plane/ReasonCode";

export function ConditionGraph({
  reasons,
  title = "Conditions",
}: {
  reasons: string[];
  title?: string;
}) {
  if (reasons.length === 0) {
    return (
      <p className="text-xs text-[var(--muted)]">
        No failing conditions reported. Passing checks require M-23 per-condition explain.
      </p>
    );
  }
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase text-[var(--muted)]">{title}</h3>
      <ul className="space-y-2">
        {reasons.map((r) => (
          <li key={r} className="rounded border border-orange-900/50 bg-orange-950/20 p-2">
            <span className="mr-2 text-rose-400" aria-label="failed">
              ✕
            </span>
            <ReasonCode code={r} />
          </li>
        ))}
      </ul>
    </div>
  );
}
