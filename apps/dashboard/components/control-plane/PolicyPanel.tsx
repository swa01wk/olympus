import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import { StatusBadge } from "@/components/status/StatusBadge";
import type { ActionRequest } from "@/lib/contracts/entity-types";

export function PolicyPanel({
  actions,
  policy,
}: {
  actions: ActionRequest[];
  policy: Record<string, unknown>;
}) {
  const denied = actions.filter((a) => a.status === "DENIED");
  const pending = actions.filter((a) => a.status === "PENDING_APPROVAL");
  const deniedCount = Number(policy.denied_actions ?? denied.length);

  return (
    <Panel title="Policy / Tool Gateway" stateRail={denied.length ? "blocked" : "neutral"} actions={<FixtureBadge />}>
      <p className="mb-2 text-xs text-[var(--muted)]">Denied (server): {deniedCount}</p>
      <ul className="space-y-2 text-xs">
        {denied.slice(0, 5).map((a) => (
          <li key={a.id} className="rounded border border-rose-900/40 p-2">
            <span className="font-mono">{a.tool}</span> — {a.resource}.{a.action}{" "}
            <StatusBadge value={a.status} />
          </li>
        ))}
        {pending.length > 0 && (
          <li className="text-violet-300">Pending approval: {pending.length}</li>
        )}
      </ul>
    </Panel>
  );
}
