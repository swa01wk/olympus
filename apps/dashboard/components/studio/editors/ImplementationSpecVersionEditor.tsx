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
import { postImplementationSpecVersion } from "@/src/api/commands";
import { invalidateCycleQueries } from "@/src/api/hooks/invalidate-cycle";
import { queryKeys } from "@/src/api/query-keys";
import { useQueryClient } from "@tanstack/react-query";

type Row = Record<string, unknown>;

const API_FIELDS: FieldSpec[] = [
  { key: "method", label: "Method" },
  { key: "path", label: "Path" },
  { key: "contract_key", label: "Contract key" },
];

const SCHEMA_FIELDS: FieldSpec[] = [
  { key: "name", label: "Name" },
  { key: "description", label: "Description", kind: "textarea" },
];

const DATA_CHANGE_FIELDS: FieldSpec[] = [
  { key: "kind", label: "Kind" },
  { key: "description", label: "Description", kind: "textarea" },
];

const TEST_FIELDS: FieldSpec[] = [
  { key: "kind", label: "Kind", kind: "select", options: ["unit", "integration", "api"] },
  { key: "ac_keys", label: "AC keys (comma-separated)", kind: "csv" },
  { key: "description", label: "Description", kind: "textarea" },
];

const COVERAGE_FIELDS: FieldSpec[] = [
  { key: "ac_key", label: "AC key" },
  { key: "locations", label: "Locations (comma-separated)", kind: "csv" },
];

function withoutBlankContractKeys(rows: Row[]): Row[] {
  return rows.map((r) => (r.contract_key === "" ? { ...r, contract_key: null } : r));
}

export function ImplementationSpecBodyForm({
  value,
  onChange,
}: {
  value: Row;
  onChange: (next: Row) => void;
}) {
  const set = (key: string, next: unknown) => onChange({ ...value, [key]: next });
  return (
    <>
      <TextField
        label="Summary"
        multiline
        value={asText(value.summary)}
        onChange={(v) => set("summary", v)}
      />
      <StringListField
        legend="Components"
        itemLabel="component"
        items={asStringList(value.components)}
        onChange={(v) => set("components", v)}
      />
      <StringListField
        legend="File scope"
        itemLabel="file scope entry"
        items={asStringList(value.file_scope)}
        onChange={(v) => set("file_scope", v)}
      />
      <ObjectListField
        legend="APIs"
        itemLabel="API"
        fields={API_FIELDS}
        items={asRows(value.apis)}
        onChange={(v) => set("apis", withoutBlankContractKeys(v))}
      />
      <ObjectListField
        legend="Schemas"
        itemLabel="schema"
        fields={SCHEMA_FIELDS}
        items={asRows(value.schemas)}
        onChange={(v) => set("schemas", v)}
      />
      <ObjectListField
        legend="Data changes"
        itemLabel="data change"
        fields={DATA_CHANGE_FIELDS}
        items={asRows(value.data_changes)}
        onChange={(v) => set("data_changes", v)}
      />
      <StringListField
        legend="Integration points"
        itemLabel="integration point"
        items={asStringList(value.integration_points)}
        onChange={(v) => set("integration_points", v)}
      />
      <ObjectListField
        legend="Required tests"
        itemLabel="required test"
        fields={TEST_FIELDS}
        items={asRows(value.required_tests)}
        onChange={(v) => set("required_tests", v)}
      />
      <StringListField
        legend="Architecture refs"
        itemLabel="architecture ref"
        items={asStringList(value.architecture_refs)}
        onChange={(v) => set("architecture_refs", v)}
      />
      <ObjectListField
        legend="AC coverage"
        itemLabel="AC coverage entry"
        fields={COVERAGE_FIELDS}
        items={asRows(value.ac_coverage)}
        onChange={(v) => set("ac_coverage", v)}
      />
    </>
  );
}

export function ImplementationSpecVersionEditor({
  spec,
  title,
  featureId,
  cycleId,
  onSaved,
}: {
  spec: { id: string; version: number; body: Row };
  title: string;
  featureId: string;
  cycleId: string;
  onSaved?: (newSpecId: string) => Promise<void> | void;
}) {
  const queryClient = useQueryClient();
  return (
    <SubjectVersionEditor<Row>
      title={title}
      subjectId={spec.id}
      initial={spec.body ?? {}}
      beforeVersion={spec.version}
      deliveryCycleId={cycleId}
      renderForm={(value, onChange) => (
        <ImplementationSpecBodyForm value={value} onChange={onChange} />
      )}
      fromRaw={(raw) => {
        if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
          throw new Error("Raw JSON must be an object.");
        }
        return raw as Row;
      }}
      onSave={async (value, meta) => {
        const res = await postImplementationSpecVersion(spec.id, {
          body: value,
          note: meta.note || undefined,
          delivery_cycle_id: meta.delivery_cycle_id,
        });
        invalidateCycleQueries(queryClient, cycleId);
        await queryClient.invalidateQueries({ queryKey: queryKeys.implementationSpecs(featureId) });
        await onSaved?.(res.id);
        return { id: res.id, version: res.version };
      }}
    />
  );
}
