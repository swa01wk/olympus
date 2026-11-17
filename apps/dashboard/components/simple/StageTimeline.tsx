import { journeyStages } from "@/lib/journey-progress";

export function StageTimeline({ cycleType, cycleState }: { cycleType: string; cycleState: string }) {
  const stages = journeyStages(cycleType, cycleState);
  if (stages.length === 0) return null;
  return (
    <ol className="sp-timeline" aria-label="Progress">
      {stages.map((s) => (
        <li
          key={s.id}
          className="sp-stage"
          data-status={s.status}
          aria-current={s.status === "current" ? "step" : undefined}
        >
          <div className="sp-stage-label">
            {s.status === "done" && <span aria-hidden="true">✓ </span>}
            {s.label}
          </div>
          <div className="sp-stage-hint">{s.hint}</div>
        </li>
      ))}
    </ol>
  );
}
