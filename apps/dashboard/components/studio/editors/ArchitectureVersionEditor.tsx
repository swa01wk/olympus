"use client";

import { SubjectVersionEditor } from "@/components/studio/SubjectVersionEditor";
import {
  ObjectListField,
  StringListField,
  TextField,
  asRows,
  asStringList,
  asText,
  type FieldSpec,
} from "@/components/studio/editors/form-fields";
import { postArchitectureVersion } from "@/src/api/commands";
import { invalidateCycleQueries } from "@/src/api/hooks/invalidate-cycle";
import { queryKeys } from "@/src/api/query-keys";
import type { ArchitectureView } from "@/src/api/types/product-model";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

type Row = Record<string, unknown>;

export type ArchitectureDraft = { body: Row; contracts: Row[] };

const STACK_FIELDS = [
  ["language", "Language"],
  ["web", "Web"],
  ["orm", "ORM"],
  ["tests", "Tests"],
] as const;

const COMPONENT_FIELDS: FieldSpec[] = [
  { key: "name", label: "Name" },
  { key: "layer", label: "Layer" },
  { key: "directory", label: "Directory" },
  { key: "responsibility", label: "Responsibility", kind: "textarea" },
];

const DIRECTORY_FIELDS: FieldSpec[] = [
  { key: "path", label: "Path" },
  { key: "purpose", label: "Purpose" },
];

const DECISION_FIELDS: FieldSpec[] = [
  { key: "id", label: "ID" },
  { key: "title", label: "Title" },
  { key: "decision", label: "Decision", kind: "textarea" },
  { key: "rationale", label: "Rationale", kind: "textarea" },
];

const CONTRACT_FIELDS: FieldSpec[] = [
  { key: "key", label: "Key" },
  { key: "kind", label: "Kind", kind: "select", options: ["API", "DATA", "EVENT"] },
  { key: "name", label: "Name" },
  { key: "method", label: "Method" },
  { key: "path", label: "Path" },
  { key: "description", label: "Description", kind: "textarea" },
];

export function contractRows(contracts: ArchitectureView["contracts"]): Row[] {
  return contracts.map((c) => {
    const def = c.definition ?? {};
    return {
      key: c.key,
      kind: c.kind,
      name: c.name,
      method: asText(def.method),
      path: asText(def.path),
      description: asText(def.description),
    };
  });
}

function isObject(value: unknown): value is Row {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function ArchitectureBodyForm({
  value,
  onChange,
}: {
  value: ArchitectureDraft;
  onChange: (next: ArchitectureDraft) => void;
}) {
  const { body } = value;
  const set = (key: string, next: unknown) => onChange({ ...value, body: { ...body, [key]: next } });
  const stack = isObject(body.technology_stack) ? body.technology_stack : {};
  return (
    <>
      <TextField
        label="Summary"
        multiline
        value={asText(body.summary)}
        onChange={(v) => set("summary", v)}
      />
      <fieldset>
        <legend className="ol-label">Technology stack</legend>
        <div className="ol-ws-form-item">
          {STACK_FIELDS.map(([key, label]) => (
            <TextField
              key={key}
              label={label}
              ariaLabel={`Technology stack ${label}`}
              value={asText(stack[key])}
              onChange={(v) => set("technology_stack", { ...stack, [key]: v })}
            />
          ))}
        </div>
      </fieldset>
      <ObjectListField
        legend="Components"
        itemLabel="component"
        fields={COMPONENT_FIELDS}
        items={asRows(body.components)}
        onChange={(v) => set("components", v)}
      />
      <StringListField
        legend="Layers"
        itemLabel="layer"
        items={asStringList(body.layers)}
        onChange={(v) => set("layers", v)}
      />
      <StringListField
        legend="Dependency rules"
        itemLabel="dependency rule"
        items={asStringList(body.dependency_rules)}
        onChange={(v) => set("dependency_rules", v)}
      />
      <ObjectListField
        legend="Directory conventions"
        itemLabel="directory convention"
        fields={DIRECTORY_FIELDS}
        items={asRows(body.directory_conventions)}
        onChange={(v) => set("directory_conventions", v)}
      />
      <ObjectListField
        legend="Decisions"
        itemLabel="decision"
        fields={DECISION_FIELDS}
        items={asRows(body.decisions)}
        onChange={(v) => set("decisions", v)}
      />
      <StringListField
        legend="Constraints"
        itemLabel="constraint"
        items={asStringList(body.constraints)}
        onChange={(v) => set("constraints", v)}
      />
      <StringListField
        legend="Risks"
        itemLabel="risk"
        items={asStringList(body.risks)}
        onChange={(v) => set("risks", v)}
      />
      <ObjectListField
        legend="Contracts"
        itemLabel="contract"
        fields={CONTRACT_FIELDS}
        items={value.contracts}
        onChange={(v) => onChange({ ...value, contracts: v })}
      />
    </>
  );
}

export function ArchitectureVersionEditor({
  architecture,
  projectId,
  cycleId,
}: {
  architecture: ArchitectureView;
  projectId: string;
  cycleId: string;
}) {
  const queryClient = useQueryClient();
  const initial = useMemo<ArchitectureDraft>(
    () => ({ body: architecture.body ?? {}, contracts: contractRows(architecture.contracts ?? []) }),
    [architecture.body, architecture.contracts],
  );

  return (
    <SubjectVersionEditor<ArchitectureDraft>
      title="Edit architecture"
      subjectId={architecture.id}
      initial={initial}
      beforeVersion={architecture.version}
      deliveryCycleId={cycleId}
      renderForm={(value, onChange) => <ArchitectureBodyForm value={value} onChange={onChange} />}
      fromRaw={(raw) => {
        if (!isObject(raw) || !isObject(raw.body)) {
          throw new Error('Raw JSON must be an object with a "body" object (and optional "contracts" list).');
        }
        if (raw.contracts !== undefined && !Array.isArray(raw.contracts)) {
          throw new Error('"contracts" must be a list.');
        }
        return {
          body: raw.body,
          contracts: raw.contracts === undefined ? initial.contracts : asRows(raw.contracts),
        };
      }}
      onSave={async (value, meta) => {
        const contractsChanged = JSON.stringify(value.contracts) !== JSON.stringify(initial.contracts);
        const res = await postArchitectureVersion(architecture.id, {
          body: value.body,
          ...(contractsChanged ? { contracts: value.contracts } : {}),
          note: meta.note || undefined,
          delivery_cycle_id: meta.delivery_cycle_id,
        });
        invalidateCycleQueries(queryClient, cycleId);
        await queryClient.invalidateQueries({ queryKey: queryKeys.architecture(projectId) });
        return { id: res.id, version: res.version };
      }}
    />
  );
}
