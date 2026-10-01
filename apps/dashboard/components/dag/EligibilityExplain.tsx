import { ConditionGraph } from "@/components/control-plane/ConditionGraph";
import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";

export function EligibilityExplain({
  eligible,
  reasons,
}: {
  eligible: boolean;
  reasons: string[];
}) {
  return (
    <Panel
      title="Eligibility"
      stateRail={eligible ? "complete" : "blocked"}
      actions={<FixtureBadge />}
    >
      <p className="mb-2 text-sm">
        Server verdict:{" "}
        <strong className={eligible ? "text-emerald-300" : "text-orange-300"}>
          {eligible ? "eligible" : "not eligible"}
        </strong>
      </p>
      {!eligible && <ConditionGraph reasons={reasons} title="Failing reasons" />}
      {eligible && (
        <p className="text-xs text-[var(--muted)]">
          Passing condition breakdown requires M-23; only failures are returned today.
        </p>
      )}
    </Panel>
  );
}
