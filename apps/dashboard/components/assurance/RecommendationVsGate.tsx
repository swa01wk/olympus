import { StatusBadge } from "@/components/status/StatusBadge";
import type { Gate } from "@/lib/contracts/entity-types";

export function RecommendationVsGate({ gate }: { gate: Gate }) {
  const rec = gate.recommendation as Record<string, unknown> | null | undefined;
  const recLabel =
    (rec?.recommendation as string) ??
    (rec?.recommended as string) ??
    "—";
  return (
    <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr]">
      <div className="rounded-lg border border-dashed border-slate-600 p-4">
        <div className="text-xs font-medium uppercase text-[var(--muted)]">Agent recommendation — advisory</div>
        <div className="mt-2 font-mono text-lg">{recLabel}</div>
      </div>
      <div className="flex items-center justify-center text-2xl font-bold text-[var(--muted)]" aria-hidden>
        ≠
      </div>
      <div className="rounded-lg border border-slate-500 p-4">
        <div className="text-xs font-medium uppercase text-[var(--muted)]">Olympus Gate — authoritative</div>
        <div className="mt-2 flex items-center gap-2">
          <StatusBadge value={gate.status} preferred={gate.status === "PASS" ? "complete" : "failed"} />
          {gate.finalized_by && (
            <span className="text-xs text-[var(--muted)]">{gate.finalized_by}</span>
          )}
        </div>
        {gate.reasons && gate.reasons.length > 0 && (
          <ul className="mt-2 list-inside list-disc text-xs text-rose-300">
            {gate.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
