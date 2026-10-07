"use client";

export function EligibilityChecklist({
  eligible,
  conditions,
}: {
  eligible: boolean;
  conditions: { name: string; ok: boolean; reasons: string[] }[];
}) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">
        Release eligibility:{" "}
        <strong className={eligible ? "text-[var(--success)]" : "text-[var(--warning)]"}>
          {eligible ? "All predicates pass" : "Blocked"}
        </strong>
      </p>
      <ul className="flex flex-col gap-2">
        {conditions.map((c) => (
          <li
            key={c.name}
            className="border border-[var(--border)] rounded p-3 text-sm"
          >
            <div className="flex items-center gap-2">
              <span aria-hidden>{c.ok ? "✓" : "○"}</span>
              <strong>{c.name}</strong>
            </div>
            {!c.ok && c.reasons.length > 0 && (
              <ul className="mt-2 ml-6 list-disc ol-muted">
                {c.reasons.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
