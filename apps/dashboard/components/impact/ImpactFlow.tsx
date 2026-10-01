import type { ImpactAssessment } from "@/lib/contracts/entity-types";

export function ImpactFlow({ assessment }: { assessment: ImpactAssessment }) {
  const byKind = new Map<string, typeof assessment.items>();
  assessment.items.forEach((item) => {
    const k = item.kind;
    if (!byKind.has(k)) byKind.set(k, []);
    byKind.get(k)!.push(item);
  });

  return (
    <div className="flex gap-3 overflow-x-auto">
      {["DIRECT", "TRANSITIVE", "CANDIDATE", "SEMANTIC_CANDIDATE"].map((kind) => (
        <div key={kind} className="min-w-[180px] rounded border border-[var(--border)] bg-[var(--surface)] p-2">
          <h3 className="text-[10px] font-semibold uppercase text-[var(--muted)]">{kind}</h3>
          <ul className="mt-2 space-y-1 text-xs">
            {(byKind.get(kind) ?? []).map((item) => (
              <li key={item.id} className="font-mono">
                {item.stable_key}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
