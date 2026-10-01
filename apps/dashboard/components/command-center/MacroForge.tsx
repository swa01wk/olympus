import type { MacroBandVM } from "@/lib/view-models/macro-forge";

const displayClass: Record<string, string> = {
  NOT_STARTED: "border-[var(--border)] text-[var(--muted)]",
  READY: "border-sky-700 text-sky-200",
  ACTIVE: "border-sky-400 bg-sky-950/30 text-sky-100 animate-pulse",
  WAITING: "border-violet-700 text-violet-200",
  BLOCKED: "border-orange-600 text-orange-200",
  FAILED: "border-rose-600 text-rose-200",
  COMPLETE: "border-emerald-700 text-emerald-200",
};

export function MacroForge({ bands }: { bands: MacroBandVM[] }) {
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-max items-stretch gap-1">
        {bands.map((b, i) => (
          <div key={b.id} className="flex items-stretch">
            <div
              className={`flex min-w-[88px] flex-col rounded border px-2 py-2 text-center ${displayClass[b.display] ?? displayClass.NOT_STARTED}`}
            >
              <span className="text-[10px] font-semibold uppercase tracking-wide">{b.label}</span>
              <span className="mt-1 font-mono text-[9px] opacity-70">{b.display.replace("_", " ")}</span>
            </div>
            {b.gateAfter && (
              <div
                className="mx-1 flex w-6 flex-col items-center justify-center text-[9px] text-amber-500"
                title="Approval gate"
              >
                ◆
                <span>APPROVAL</span>
              </div>
            )}
            {i < bands.length - 1 && !b.gateAfter && (
              <div className="flex w-4 items-center text-[var(--muted)]" aria-hidden>
                →
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
