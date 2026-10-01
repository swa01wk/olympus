import { Panel } from "@/components/design/Panel";
import { FixtureBadge } from "@/components/states/FixtureBadge";
import type { TaskContract } from "@/lib/contracts/entity-types";

export function ContractView({ contract }: { contract: TaskContract }) {
  const b = contract.body;
  return (
    <Panel title="TaskContract" stateRail="neutral" actions={<FixtureBadge />}>
      <dl className="grid gap-2 text-xs md:grid-cols-2">
        <Field label="key" value={`${contract.key}:v${contract.version}`} />
        <Field label="status" value={contract.status} />
        <Field label="objective" value={b.objective} />
        <Field label="work_type" value={b.work_type} />
        <Field label="executor_kind" value={b.executor_kind} />
        <Field label="model_alias" value={b.model_alias ?? "—"} />
        <Field label="agent_profile" value={b.agent_profile ?? "—"} />
      </dl>
      <Section title="allowed_scope" items={b.allowed_scope} />
      <Section title="allowed_actions" items={b.allowed_actions} />
      <Section title="required_outputs" items={b.required_outputs} />
      <Section
        title="inputs"
        items={b.inputs.map((i) => `${i.ref_type}:${i.key ?? i.ref_id}@${i.version ?? "—"}`)}
      />
    </Panel>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[var(--muted)]">{label}</dt>
      <dd className="font-mono">{value}</dd>
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-3">
      <h4 className="text-[10px] font-semibold uppercase text-[var(--muted)]">{title}</h4>
      <ul className="mt-1 list-inside list-disc font-mono text-[11px]">
        {items.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
    </div>
  );
}
